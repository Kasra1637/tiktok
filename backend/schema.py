"""Schema bootstrap and idempotent migrations.

`apply_schema(conn, ...)` is called by `db.init_db`. It owns every CREATE TABLE,
ADD COLUMN migration, and curated-template seeding/backfill the app ships with.
The few media helpers the backfills need (`_analysis_frame_path`,
`_normalize_analysis_frame`, `_normalize_template_thumbnail`, `GENERATED_ID_RE`)
stay owned by `server` and are passed in by `db.init_db`, so this module never
imports the composition root.
"""

import json
import logging
import uuid

import pipeline
import template_library
from models import now_iso

logger = logging.getLogger(__name__)


async def apply_schema(conn, *, analysis_frame_path, normalize_analysis_frame,
                       normalize_template_thumbnail, generated_id_re):
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            tiktok_url TEXT,
            niche TEXT,
            video_platform_id TEXT,
            creator TEXT,
            creator_display TEXT,
            title TEXT,
            description TEXT,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            bookmark_count INTEGER DEFAULT 0,
            duration REAL DEFAULT 0,
            thumbnail_url TEXT,
            direct_video_url TEXT,
            hashtags TEXT,
            song_id TEXT,
            song_title TEXT,
            song_artist TEXT,
            song_album TEXT,
            song_duration INTEGER DEFAULT 0,
            song_cover_url TEXT,
            subtitles_url TEXT,
            subtitles_language TEXT,
            is_ad INTEGER DEFAULT 0,
            creator_followers INTEGER DEFAULT 0,
            creator_following INTEGER DEFAULT 0,
            creator_verified INTEGER DEFAULT 0,
            creator_bio TEXT,
            creator_avatar TEXT,
            status TEXT DEFAULT 'metadata_ready',
            local_video_path TEXT,
            last_analysis_id TEXT,
            error TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            video_id TEXT,
            frames TEXT,
            facial_expressions TEXT,
            body_language_gestures TEXT,
            pacing_cuts TEXT,
            text_overlays_timing TEXT,
            audio_cues_inferred TEXT,
            hook_summary TEXT,
            effectiveness_score INTEGER,
            key_hook_frame_index INTEGER,
            replicable_mechanics TEXT,
            created_at TEXT
        );

        -- Durable backups for the small extracted JPEGs listed in
        -- analyses.frames. The public frame URLs are metadata only; the
        -- actual files otherwise disappear on a clean container deploy.
        CREATE TABLE IF NOT EXISTS analysis_frame_assets (
            video_hash TEXT NOT NULL,
            filename TEXT NOT NULL,
            image_bytes BLOB NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (video_hash, filename)
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_frame_assets_lookup
            ON analysis_frame_assets (video_hash, filename);

        CREATE TABLE IF NOT EXISTS customizations (
            id TEXT PRIMARY KEY,
            video_id TEXT,
            analysis_id TEXT,
            mode TEXT,
            person_photo_url TEXT,
            reference_frame_url TEXT,
            environment TEXT,
            background TEXT,
            clothing TEXT,
            custom_instructions TEXT,
            generation_spec TEXT,
            generated_images TEXT,
            generated_image_url TEXT,
            video_title TEXT,
            video_niche TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS video_jobs (
            id TEXT PRIMARY KEY,
            customization_id TEXT,
            video_id TEXT,
            brand_name TEXT,
            brand_goal TEXT,
            brand_details TEXT,
            target_duration_seconds INTEGER,
            prompt_breakdown TEXT,
            full_prompt_text TEXT,
            reference_image_ids TEXT,
            selected_image_ids TEXT,
            use_original_sound INTEGER DEFAULT 0,
            sound_reference TEXT,
            status TEXT DEFAULT 'prompt_ready',
            openrouter_job_id TEXT,
            video_url TEXT,
            error TEXT,
            created_at TEXT,
            requested_at TEXT
        );

        CREATE TABLE IF NOT EXISTS brand_profiles (
            id TEXT PRIMARY KEY,
            website_url TEXT,
            brand_name TEXT,
            brand_description TEXT,
            niche TEXT,
            products_services TEXT,
            target_audience TEXT,
            ideal_customer_profile TEXT,
            differentiation TEXT,
            tone_voice TEXT,
            raw_extracted_text TEXT,
            created_at TEXT,
            updated_at TEXT,
            appstore_url TEXT,
            play_url TEXT,
            support_urls TEXT,
            notes TEXT,
            app_category TEXT,
            platforms TEXT,
            core_features TEXT,
            primary_use_cases TEXT,
            problems_solved TEXT,
            icp_segments TEXT,
            desired_outcomes TEXT,
            known_limitations TEXT,
            must_not_show TEXT,
            usage_moments TEXT,
            proof_moment TEXT,
            viewer_objections TEXT,
            outcome_statements TEXT,
            claims_approved TEXT,
            claims_review TEXT,
            claims_banned TEXT,
            ctas TEXT,
            video_themes TEXT,
            status TEXT DEFAULT 'draft',
            version INTEGER DEFAULT 1,
            approved_at TEXT,
            last_research_at TEXT,
            research_sources TEXT,
            pending_research TEXT
        );

        CREATE TABLE IF NOT EXISTS generated_images (
            id TEXT PRIMARY KEY,
            origin TEXT,
            job_id TEXT,
            target_image_url TEXT,
            user_id TEXT DEFAULT 'anonymous',
            image_bytes BLOB,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS hook_templates (
            id TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            notes TEXT,
            source_video_id TEXT,
            source_analysis_id TEXT,
            source_tiktok_url TEXT,
            source_creator TEXT,
            source_title TEXT,
            thumbnail_url TEXT,
            thumbnail_bytes BLOB,
            facial_expressions TEXT,
            body_language_gestures TEXT,
            pacing_cuts TEXT,
            text_overlays_timing TEXT,
            audio_cues_inferred TEXT,
            hook_summary TEXT,
            effectiveness_score INTEGER,
            replicable_mechanics TEXT,
            prompt_template TEXT,
            reference_video_path TEXT,
            song_title TEXT,
            song_artist TEXT,
            times_used INTEGER DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            app_categories TEXT,
            audiences TEXT,
            objective TEXT,
            opening_structure TEXT,
            hook_seconds INTEGER,
            middle_structure TEXT,
            continuation_structure TEXT,
            cta_pattern TEXT,
            visual_style TEXT,
            camera_pacing TEXT,
            required_assets TEXT,
            default_duration INTEGER,
            content_slots TEXT,
            example_preview TEXT,
            outcome TEXT,
            version INTEGER DEFAULT 1,
            archived INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            evidence_note TEXT,
            trend_evidence TEXT,
            origin TEXT DEFAULT 'bookmark',
            review_status TEXT DEFAULT 'approved',
            brand_profile_id TEXT,
            angle_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_templates_brand
            ON hook_templates (brand_profile_id, archived);

        CREATE TABLE IF NOT EXISTS content_angles (
            id TEXT PRIMARY KEY,
            brand_profile_id TEXT,
            kind TEXT,
            label TEXT,
            target_audience TEXT,
            user_problem TEXT,
            hook_promise TEXT,
            app_feature TEXT,
            desired_emotion TEXT,
            viewer_outcome TEXT,
            recommended_cta TEXT,
            claims_to_respect TEXT,
            evidence TEXT,
            rank INTEGER DEFAULT 0,
            created_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_content_angles_profile
            ON content_angles (brand_profile_id, rank);

        CREATE TABLE IF NOT EXISTS template_favorites (
            template_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT,
            PRIMARY KEY (template_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS studio_projects (
            id TEXT PRIMARY KEY,
            brand_profile_id TEXT,
            content_angle_id TEXT,
            template_id TEXT,
            template_version INTEGER,
            objective TEXT,
            audience TEXT,
            duration_seconds INTEGER,
            tone TEXT,
            hook_line TEXT,
            script TEXT,
            plan_trimmed_chars INTEGER DEFAULT 0,
            beat_timeline TEXT,
            location TEXT,
            visual_direction TEXT,
            feature_emphasis TEXT,
            demo_brief TEXT,
            overlays TEXT,
            voice_direction TEXT,
            sound_direction TEXT,
            cta TEXT,
            assets TEXT,
            safety_report TEXT,
            safety_summary TEXT,
            strategy TEXT,
            strategy_version INTEGER DEFAULT 0,
            hook_seconds INTEGER DEFAULT 0,
            extend_intent INTEGER DEFAULT 1,
            script_version INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            created_at TEXT,
            updated_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_studio_projects_user
            ON studio_projects (user_id, updated_at);

        CREATE TABLE IF NOT EXISTS generations (
            id TEXT PRIMARY KEY,
            studio_project_id TEXT,
            brand_profile_id TEXT,
            template_id TEXT,
            template_version INTEGER,
            script_version INTEGER,
            model TEXT,
            model_id TEXT,
            requested_duration INTEGER,
            duration INTEGER,
            status TEXT DEFAULT 'submitted',
            segment_role TEXT DEFAULT 'primary',
            segment_index INTEGER DEFAULT 0,
            strategy_version INTEGER DEFAULT 0,
            continuity TEXT,
            post_kit TEXT,
            tiktok_url TEXT,
            tiktok_views INTEGER,
            tiktok_views_at TEXT,
            approved INTEGER DEFAULT 0,
            approved_at TEXT,
            trim_to_seconds INTEGER DEFAULT 0,
            final_beat TEXT,
            attempt INTEGER DEFAULT 1,
            openrouter_job_id TEXT,
            polling_url TEXT,
            video_url TEXT,
            r2_url TEXT,
            prompt_used TEXT,
            adjustments TEXT,
            error TEXT,
            storage_error TEXT,
            retryable INTEGER DEFAULT 1,
            requested_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            location TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_generations_user
            ON generations (user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_generations_project
            ON generations (studio_project_id, created_at);

        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            brand_profile_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            name TEXT,
            notes TEXT,
            file_path TEXT NOT NULL,
            preview_path TEXT,
            content_type TEXT,
            duration_seconds REAL,
            face_count INTEGER,
            rights_confirmed INTEGER DEFAULT 0,
            label TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_assets_profile
            ON assets (brand_profile_id, status);

        CREATE TABLE IF NOT EXISTS feedback_events (
            id TEXT PRIMARY KEY,
            brand_profile_id TEXT,
            studio_project_id TEXT,
            generation_id TEXT,
            template_id TEXT,
            event TEXT,
            signal TEXT,
            reason TEXT,
            detail TEXT,
            step TEXT,
            created_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_app
            ON feedback_events (brand_profile_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_feedback_event
            ON feedback_events (event, reason);
        CREATE INDEX IF NOT EXISTS idx_feedback_generation
            ON feedback_events (user_id, generation_id, created_at);

        CREATE TABLE IF NOT EXISTS video_assets (
            job_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'anonymous',
            r2_url TEXT NOT NULL,
            phase TEXT DEFAULT 'hook',
            source_video_id TEXT,
            source_hook_template_id TEXT,
            duration INTEGER,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_video_assets_user
            ON video_assets (user_id, created_at);

        CREATE TABLE IF NOT EXISTS model_requests (
            id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            modality TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed',
            latency_ms INTEGER,
            error TEXT,
            brand_profile_id TEXT,
            studio_project_id TEXT,
            generation_id TEXT,
            template_id TEXT,
            research_run_id TEXT,
            created_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_model_requests_user
            ON model_requests (user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_model_requests_operation
            ON model_requests (operation, status);

        CREATE TABLE IF NOT EXISTS asset_events (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            reason TEXT NOT NULL,
            brand_profile_id TEXT,
            studio_project_id TEXT,
            generation_id TEXT,
            asset_id TEXT,
            asset_kind TEXT,
            filename TEXT,
            created_at TEXT,
            user_id TEXT DEFAULT 'anonymous'
        );
        CREATE INDEX IF NOT EXISTS idx_asset_events_user
            ON asset_events (user_id, created_at);
    """)
    await conn.commit()

    # Migration: add columns that may be missing on a pre-existing DB (e.g. on Render's
    # persistent-ish free-tier disk from a previous deploy of this table).
    cursor = await conn.execute("PRAGMA table_info(brand_profiles)")
    existing_cols = {row[1] for row in await cursor.fetchall()}
    for col in ("ideal_customer_profile", "differentiation"):
        if col not in existing_cols:
            await conn.execute(f"ALTER TABLE brand_profiles ADD COLUMN {col} TEXT")
    for col in (
        "appstore_url", "play_url", "support_urls", "notes", "app_category",
        "platforms", "core_features", "primary_use_cases",
        "problems_solved", "icp_segments", "desired_outcomes",
        "known_limitations", "must_not_show", "usage_moments", "proof_moment",
        "viewer_objections", "outcome_statements", "claims_approved", "claims_review",
        "claims_banned", "ctas", "video_themes", "status",
        "approved_at", "last_research_at", "research_sources",
        "pending_research",
    ):
        if col not in existing_cols:
            default = " DEFAULT 'draft'" if col == "status" else ""
            await conn.execute(f"ALTER TABLE brand_profiles ADD COLUMN {col} TEXT{default}")
    if "version" not in existing_cols:
        await conn.execute("ALTER TABLE brand_profiles ADD COLUMN version INTEGER DEFAULT 1")
    await conn.commit()

    # Migration: Template Library columns for hook_templates.
    cursor = await conn.execute("PRAGMA table_info(hook_templates)")
    template_cols = {row[1] for row in await cursor.fetchall()}
    for col in (
        "app_categories", "audiences", "objective", "opening_structure",
        "middle_structure", "continuation_structure", "cta_pattern", "visual_style",
        "camera_pacing", "required_assets", "content_slots", "evidence_note",
        "trend_evidence", "outcome",
        "origin", "review_status",
    ):
        if col not in template_cols:
            await conn.execute(f"ALTER TABLE hook_templates ADD COLUMN {col} TEXT")
    for col, decl in (
        ("hook_seconds", "INTEGER"),
        ("default_duration", "INTEGER"),
        ("version", "INTEGER DEFAULT 1"),
        ("archived", "INTEGER DEFAULT 0"),
        ("is_favorite", "INTEGER DEFAULT 0"),
    ):
        if col not in template_cols:
            await conn.execute(f"ALTER TABLE hook_templates ADD COLUMN {col} {decl}")
    await conn.execute(
        "UPDATE hook_templates SET origin = 'bookmark' "
        "WHERE origin IS NULL OR origin = ''"
    )
    await conn.commit()

    # Migration: drop and recreate cache tables if they're missing new columns.
    cache_tables_to_check = {
        "videos": "is_ad",
        "video_jobs": "use_original_sound",
    }
    for table, required_col in cache_tables_to_check.items():
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cursor.fetchall()}
        if cols and required_col not in cols:
            logger.info(f"Migration: dropping and recreating {table} (missing column '{required_col}')")
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
    await conn.commit()

    # Retired feed caches.
    for table in (
        "trending_videos", "trending_cache_meta",
        "niche_cache_meta", "curated_videos",
    ):
        await conn.execute(f"DROP TABLE IF EXISTS {table}")
        logger.info(f"Migration: dropped retired feed-cache table {table}")
    await conn.commit()

    # Recreate any tables that were just dropped
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            tiktok_url TEXT,
            niche TEXT,
            video_platform_id TEXT,
            creator TEXT,
            creator_display TEXT,
            title TEXT,
            description TEXT,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            bookmark_count INTEGER DEFAULT 0,
            duration REAL DEFAULT 0,
            thumbnail_url TEXT,
            direct_video_url TEXT,
            hashtags TEXT,
            song_id TEXT,
            song_title TEXT,
            song_artist TEXT,
            song_album TEXT,
            song_duration INTEGER DEFAULT 0,
            song_cover_url TEXT,
            subtitles_url TEXT,
            subtitles_language TEXT,
            is_ad INTEGER DEFAULT 0,
            creator_followers INTEGER DEFAULT 0,
            creator_following INTEGER DEFAULT 0,
            creator_verified INTEGER DEFAULT 0,
            creator_bio TEXT,
            creator_avatar TEXT,
            status TEXT DEFAULT 'metadata_ready',
            local_video_path TEXT,
            last_analysis_id TEXT,
            error TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS video_jobs (
            id TEXT PRIMARY KEY,
            customization_id TEXT,
            video_id TEXT,
            brand_name TEXT,
            brand_goal TEXT,
            brand_details TEXT,
            target_duration_seconds INTEGER,
            prompt_breakdown TEXT,
            full_prompt_text TEXT,
            reference_image_ids TEXT,
            selected_image_ids TEXT,
            use_original_sound INTEGER DEFAULT 0,
            sound_reference TEXT,
            status TEXT DEFAULT 'prompt_ready',
            openrouter_job_id TEXT,
            video_url TEXT,
            error TEXT,
            created_at TEXT,
            requested_at TEXT
        );
    """)
    await conn.commit()

    # Migration: add user_id column to all per-user tables.
    user_id_tables = [
        "videos", "analyses", "customizations", "video_jobs",
        "brand_profiles", "hook_templates",
        "studio_projects", "content_angles", "generations",
        "assets",
        "feedback_events",
    ]
    for table in user_id_tables:
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cursor.fetchall()}
        if "user_id" not in cols:
            logger.info(f"Migration: adding user_id column to {table}")
            await conn.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id TEXT DEFAULT 'anonymous'"
            )
    await conn.commit()

    # Migration: the app-specific influencer workflow.
    influencer_migrations = [
        ("studio_projects", "strategy", "TEXT"),
        ("studio_projects", "strategy_version", "INTEGER DEFAULT 0"),
        ("studio_projects", "strategy_script_version", "INTEGER DEFAULT 0"),
        ("studio_projects", "camera_setup", "TEXT NOT NULL DEFAULT 'handheld'"),
        ("studio_projects", "hook_seconds", "INTEGER DEFAULT 0"),
        ("studio_projects", "extend_intent", "INTEGER DEFAULT 1"),
        ("generations", "segment_index", "INTEGER DEFAULT 0"),
        ("generations", "strategy_version", "INTEGER DEFAULT 0"),
        ("generations", "camera_setup", "TEXT NOT NULL DEFAULT 'handheld'"),
        ("generations", "continuity", "TEXT"),
        ("generations", "approved", "INTEGER DEFAULT 0"),
        ("generations", "approved_at", "TEXT"),
        ("generations", "trim_to_seconds", "INTEGER DEFAULT 0"),
        ("studio_projects", "demo_brief", "TEXT"),
        ("studio_projects", "plan_trimmed_chars", "INTEGER DEFAULT 0"),
        ("generations", "idempotency_key", "TEXT"),
        ("content_angles", "goal_variant", "INTEGER DEFAULT 0"),
        ("content_angles", "origin", "TEXT DEFAULT 'generated'"),
        ("generations", "post_kit", "TEXT"),
        ("generations", "tiktok_url", "TEXT"),
        ("generations", "tiktok_views", "INTEGER"),
        ("generations", "tiktok_views_at", "TEXT"),
        ("content_angles", "viewer_outcome", "TEXT"),
        ("studio_projects", "angle_scene_note", "TEXT"),
        ("studio_projects", "location", "TEXT"),
        ("generations", "location", "TEXT"),
    ]
    for table, column, decl in influencer_migrations:
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        cols = {r[1] for r in await cursor.fetchall()}
        if column not in cols:
            logger.info(f"Migration: adding {table}.{column}")
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    await conn.commit()

    await conn.execute(
        "UPDATE content_angles SET origin = 'generated' WHERE origin IS NULL OR origin = ''"
    )
    await conn.commit()

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_generations_chain "
        "ON generations (studio_project_id, segment_index)"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_generations_idempotency "
        "ON generations (user_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL AND idempotency_key != ''"
    )
    await conn.commit()

    # Seed the curated template library once.
    cursor = await conn.execute("SELECT name FROM hook_templates WHERE origin = 'curated'")
    seeded_names = {(r[0] or "").strip().lower() for r in await cursor.fetchall()}
    seeded = 0
    for tpl in template_library.curated_template_rows():
        if tpl["name"].strip().lower() in seeded_names:
            continue
        now = now_iso()
        await conn.execute(
            """INSERT INTO hook_templates
               (id, name, category, notes, app_categories, audiences, objective,
                  opening_structure, hook_seconds, middle_structure, visual_style,
                  camera_pacing, required_assets, default_duration,
                  content_slots, evidence_note, outcome, version, archived, is_favorite,
                  origin, review_status, times_used, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), tpl["name"],
                template_library.normalize_category(tpl["category"]), "",
                json.dumps(tpl.get("app_categories") or []),
                json.dumps(tpl.get("audiences") or []),
                template_library.normalize_objective(tpl.get("objective")),
                tpl["opening_structure"], int(tpl["hook_seconds"] or 3),
                tpl["middle_structure"], tpl["visual_style"],
                tpl["camera_pacing"], json.dumps(tpl.get("required_assets") or []),
                int(tpl["default_duration"] or 10),
                json.dumps(tpl.get("content_slots") or {}), tpl.get("evidence_note") or "",
                tpl.get("outcome") or "",
                1, 0, 0, "curated", "approved", 0, now, now, "system",
            ),
        )
        seeded += 1
    if seeded:
        logger.info("Seeded %d curated hook template(s)", seeded)

    now = now_iso()
    for tpl in template_library.CURATED_TEMPLATES:
        desired_slots = json.dumps(tpl.get("content_slots") or {})
        cursor = await conn.execute(
            """SELECT opening_structure, hook_seconds, middle_structure,
                      visual_style, camera_pacing, content_slots, default_duration,
                      outcome
                 FROM hook_templates
                WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
            (tpl["name"].strip().lower(),),
        )
        current = await cursor.fetchone()
        if current is not None:
            stored_slots = current[5]
            if isinstance(stored_slots, str):
                try:
                    stored_slots = json.loads(stored_slots)
                except (json.JSONDecodeError, TypeError):
                    stored_slots = None
            already_current = (
                current[0] == tpl["opening_structure"]
                and int(current[1] or 0) == int(tpl["hook_seconds"] or 3)
                and (current[2] or "") == tpl["middle_structure"]
                and (current[3] or "") == tpl["visual_style"]
                and (current[4] or "") == tpl["camera_pacing"]
                and stored_slots == (tpl.get("content_slots") or {})
                and int(current[6] or 0) == int(tpl["default_duration"] or 10)
            )
            if already_current:
                continue
        await conn.execute(
            """UPDATE hook_templates
               SET opening_structure = ?, hook_seconds = ?, middle_structure = ?,
                   visual_style = ?, camera_pacing = ?, content_slots = ?,
                   default_duration = ?, version = COALESCE(version, 1) + 1,
                   updated_at = ?
               WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
            (
                tpl["opening_structure"], int(tpl["hook_seconds"] or 3),
                tpl["middle_structure"], tpl["visual_style"], tpl["camera_pacing"],
                desired_slots,
                int(tpl["default_duration"] or 10),
                now, tpl["name"].strip().lower(),
            ),
        )
        desired_outcome = tpl.get("outcome") or ""
        stored_outcome = current[7] if current is not None else None
        if stored_outcome != desired_outcome:
            await conn.execute(
                """UPDATE hook_templates
                    SET outcome = ?, updated_at = ?
                    WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
                (desired_outcome, now, tpl["name"].strip().lower()),
            )

    # Face-only library.
    retired_names = (
        "Before and After",
        "Quick App Demonstration",
        "Feature Reveal",
        "Competitor Alternative",
        "Fast Tutorial",
        "Screen-Recording Reveal",
        "Problem, App, Result",
        "Three Taps to Solve This",
    )
    face_only = json.dumps(["character_reference"])
    cursor = await conn.execute(
        "SELECT name, required_assets, archived FROM hook_templates "
        "WHERE origin = 'curated'"
    )
    for row in await cursor.fetchall():
        name, current_raw, archived = (row[0] or ""), (row[1] or "[]"), (row[2] or 0)
        if name in retired_names:
            if not archived:
                await conn.execute(
                    "UPDATE hook_templates SET archived = 1 WHERE name = ? "
                    "AND origin = 'curated'",
                    (name,),
                )
                logger.info("Archived retired template %s", name)
            continue
        try:
            current = json.loads(current_raw)
        except (json.JSONDecodeError, TypeError):
            current = None
        if current != ["character_reference"]:
            await conn.execute(
                "UPDATE hook_templates SET required_assets = ? "
                "WHERE name = ? AND origin = 'curated'",
                (face_only, name),
            )
            logger.info(
                "Backfilled %s: required_assets %s -> %s", name, current, face_only
            )

    await conn.commit()

    # Migration: feedback_events gains a `signal` column.
    cursor = await conn.execute("PRAGMA table_info(feedback_events)")
    if "signal" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding signal column to feedback_events")
        await conn.execute("ALTER TABLE feedback_events ADD COLUMN signal TEXT")
    await conn.commit()
    cursor = await conn.execute("PRAGMA table_info(feedback_events)")
    if "step" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding step column to feedback_events")
        await conn.execute("ALTER TABLE feedback_events ADD COLUMN step TEXT")
    await conn.commit()

    # Migration: assets gains a face count.
    cursor = await conn.execute("PRAGMA table_info(assets)")
    if "duration_seconds" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding duration_seconds column to assets")
        await conn.execute("ALTER TABLE assets ADD COLUMN duration_seconds REAL")
    await conn.commit()

    # Migration: hook_templates gains brand scoping.
    cursor = await conn.execute("PRAGMA table_info(hook_templates)")
    if "brand_profile_id" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding brand_profile_id column to hook_templates")
        await conn.execute("ALTER TABLE hook_templates ADD COLUMN brand_profile_id TEXT")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_templates_brand "
            "ON hook_templates (brand_profile_id, archived)"
        )
    await conn.commit()

    # Migration: hook_templates gains the selected angle.
    cursor = await conn.execute("PRAGMA table_info(hook_templates)")
    if "angle_id" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding angle_id column to hook_templates")
        await conn.execute("ALTER TABLE hook_templates ADD COLUMN angle_id TEXT")
    await conn.commit()

    # Migration: assets gains a face count.
    cursor = await conn.execute("PRAGMA table_info(assets)")
    if "face_count" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding face_count column to assets")
        await conn.execute("ALTER TABLE assets ADD COLUMN face_count INTEGER")
    await conn.commit()

    # Migration: generations storage_error.
    cursor = await conn.execute("PRAGMA table_info(generations)")
    if "storage_error" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding storage_error column to generations")
        await conn.execute("ALTER TABLE generations ADD COLUMN storage_error TEXT")
    await conn.commit()

    # Migration: generations final_beat.
    cursor = await conn.execute("PRAGMA table_info(generations)")
    if "final_beat" not in {row[1] for row in await cursor.fetchall()}:
        logger.info("Migration: adding final_beat column to generations")
        await conn.execute("ALTER TABLE generations ADD COLUMN final_beat TEXT")
    await conn.commit()

    # Best-effort backfill for analyses frames.
    frame_backfilled = 0
    cursor = await conn.execute("SELECT frames FROM analyses WHERE frames IS NOT NULL")
    for (frames_json,) in await cursor.fetchall():
        try:
            frame_docs = json.loads(frames_json)
        except (TypeError, ValueError):
            continue
        for frame_doc in frame_docs if isinstance(frame_docs, list) else []:
            media_url = frame_doc.get("media_url") if isinstance(frame_doc, dict) else ""
            import re as _re
            match = _re.fullmatch(r"/api/media/frames/([0-9a-f]{16})/(frame_\d{3}\.jpg)", media_url or "")
            if not match:
                continue
            video_hash, filename = match.groups()
            try:
                frame_path = analysis_frame_path(video_hash, filename)
                if not frame_path.is_file():
                    continue
                image_bytes = normalize_analysis_frame(frame_path.read_bytes())
                await conn.execute(
                    """INSERT OR IGNORE INTO analysis_frame_assets
                       (video_hash, filename, image_bytes, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (video_hash, filename, image_bytes, now_iso()),
                )
                frame_backfilled += 1
            except (OSError, ValueError) as exc:
                logger.warning("Could not backfill extracted frame %s/%s: %s", video_hash, filename, exc)
    if frame_backfilled:
        logger.info("Migration: backfilled %d durable extracted frame(s)", frame_backfilled)
    await conn.commit()

    # Migration: generated_images image_bytes.
    cursor = await conn.execute("PRAGMA table_info(generated_images)")
    generated_image_cols = {row[1] for row in await cursor.fetchall()}
    if "image_bytes" not in generated_image_cols:
        logger.info("Migration: adding durable image_bytes backup to generated_images")
        await conn.execute("ALTER TABLE generated_images ADD COLUMN image_bytes BLOB")
    await conn.commit()

    # Migration: hook_templates thumbnail_bytes/example_preview.
    cursor = await conn.execute("PRAGMA table_info(hook_templates)")
    template_cols = {row[1] for row in await cursor.fetchall()}
    if "thumbnail_bytes" not in template_cols:
        logger.info("Migration: adding durable thumbnail_bytes backup to hook_templates")
        await conn.execute("ALTER TABLE hook_templates ADD COLUMN thumbnail_bytes BLOB")
    if "example_preview" not in template_cols:
        logger.info("Migration: adding example_preview column to hook_templates")
        await conn.execute("ALTER TABLE hook_templates ADD COLUMN example_preview TEXT")
    await conn.commit()

    # Best-effort backfill for templates thumbnail.
    cursor = await conn.execute(
        "SELECT id FROM hook_templates WHERE thumbnail_bytes IS NULL"
    )
    for (template_id,) in await cursor.fetchall():
        if not generated_id_re.match(template_id or ""):
            continue
        thumbnail_path = pipeline.TEMPLATES_DIR / f"{template_id}.jpg"
        if not thumbnail_path.is_file():
            continue
        try:
            thumbnail_bytes = normalize_template_thumbnail(thumbnail_path.read_bytes())
            await conn.execute(
                "UPDATE hook_templates SET thumbnail_bytes = ? WHERE id = ?",
                (thumbnail_bytes, template_id),
            )
        except (OSError, ValueError) as exc:
            logger.warning("Could not backfill thumbnail for template %s: %s", template_id, exc)
    await conn.commit()

    # Migration: backfill the generated_images provenance registry.
    cursor = await conn.execute("SELECT COUNT(*) FROM generated_images")
    (existing_rows,) = await cursor.fetchone()
    if not existing_rows:
        backfilled = 0
        cursor = await conn.execute(
            """SELECT id, generated_images, user_id FROM customizations
               WHERE generated_images IS NOT NULL"""
        )
        for cust_id, images_json, cust_user in await cursor.fetchall():
            try:
                images = json.loads(images_json)
            except (TypeError, ValueError):
                continue
            if not isinstance(images, list):
                continue
            for image in images:
                if not isinstance(image, dict) or not image.get("id"):
                    continue
                await conn.execute(
                    """INSERT OR IGNORE INTO generated_images
                       (id, origin, job_id, target_image_url, user_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        image["id"],
                        "customize",
                        cust_id,
                        image.get("reference_frame_url") or "",
                        cust_user or "anonymous",
                        now_iso(),
                    ),
                )
                backfilled += 1

        if backfilled:
            logger.info(
                f"Migration: backfilled provenance for {backfilled} generated image(s)"
            )
        await conn.commit()
