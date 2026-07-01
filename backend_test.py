"""
Backend API testing for HookForge - TikTok Hook Analyzer (V2 with video generation)
Tests all CRUD operations, video ingestion, hook analysis, customization, and video prompt generation endpoints.
"""
import requests
import sys
import time
import json
from pathlib import Path

# Use the public backend URL from frontend/.env
BASE_URL = "https://viral-swap-1.preview.emergentagent.com/api"

class HookForgeAPITester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, message="", response_data=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ PASS: {name}")
            if message:
                print(f"   {message}")
        else:
            print(f"❌ FAIL: {name}")
            print(f"   {message}")
        
        self.test_results.append({
            "test": name,
            "passed": success,
            "message": message,
            "response_data": response_data
        })

    def test_root_endpoint(self):
        """Test root API endpoint"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            success = response.status_code == 200
            data = response.json() if success else {}
            self.log_test(
                "Root endpoint GET /api/",
                success,
                f"Status: {response.status_code}, Response: {data}",
                data
            )
            return success
        except Exception as e:
            self.log_test("Root endpoint GET /api/", False, f"Error: {str(e)}")
            return False

    def test_get_niches(self):
        """Test GET /api/niches - should return 10 niches"""
        try:
            response = requests.get(f"{self.base_url}/niches", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                niche_count = len(data)
                has_required_fields = all(
                    "key" in n and "label" in n and "icon" in n and "description" in n
                    for n in data
                )
                success = niche_count == 10 and has_required_fields
                self.log_test(
                    "GET /api/niches",
                    success,
                    f"Returned {niche_count} niches (expected 10), fields valid: {has_required_fields}",
                    data
                )
                return data if success else []
            else:
                self.log_test("GET /api/niches", False, f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.log_test("GET /api/niches", False, f"Error: {str(e)}")
            return []

    def test_get_niche_videos(self, niche_key="fitness"):
        """Test GET /api/niches/{niche_key}/videos - may take up to 20s on first load"""
        try:
            print(f"\n⏳ Fetching videos for niche '{niche_key}' (may take up to 20s on first load)...")
            response = requests.get(f"{self.base_url}/niches/{niche_key}/videos", timeout=30)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                video_count = len(data)
                has_videos = video_count > 0
                
                if has_videos:
                    # Check first video has required fields
                    first_video = data[0]
                    required_fields = ["tiktok_url", "creator", "title", "view_count", "like_count"]
                    has_required_fields = all(field in first_video for field in required_fields)
                    
                    self.log_test(
                        f"GET /api/niches/{niche_key}/videos",
                        has_required_fields,
                        f"Returned {video_count} videos, required fields present: {has_required_fields}",
                        {"count": video_count, "sample": first_video}
                    )
                    return data if has_required_fields else []
                else:
                    self.log_test(
                        f"GET /api/niches/{niche_key}/videos",
                        False,
                        f"No videos returned for niche '{niche_key}'"
                    )
                    return []
            else:
                self.log_test(
                    f"GET /api/niches/{niche_key}/videos",
                    False,
                    f"Status: {response.status_code}"
                )
                return []
        except Exception as e:
            self.log_test(f"GET /api/niches/{niche_key}/videos", False, f"Error: {str(e)}")
            return []

    def test_ingest_video(self, tiktok_url):
        """Test POST /api/videos/ingest"""
        try:
            print(f"\n⏳ Ingesting video: {tiktok_url}...")
            response = requests.post(
                f"{self.base_url}/videos/ingest",
                json={"tiktok_url": tiktok_url, "niche": "pets"},
                timeout=30
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                has_id = "id" in data
                has_url = data.get("tiktok_url") == tiktok_url
                
                self.log_test(
                    "POST /api/videos/ingest",
                    has_id and has_url,
                    f"Video ingested, ID: {data.get('id')}, Status: {data.get('status')}",
                    data
                )
                return data if has_id else None
            else:
                error_msg = response.text[:200] if response.text else "No error message"
                self.log_test(
                    "POST /api/videos/ingest",
                    False,
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
                return None
        except Exception as e:
            self.log_test("POST /api/videos/ingest", False, f"Error: {str(e)}")
            return None

    def test_get_video(self, video_id):
        """Test GET /api/videos/{video_id}"""
        try:
            response = requests.get(f"{self.base_url}/videos/{video_id}", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    f"GET /api/videos/{video_id}",
                    True,
                    f"Video retrieved, Status: {data.get('status')}",
                    data
                )
                return data
            else:
                self.log_test(
                    f"GET /api/videos/{video_id}",
                    False,
                    f"Status: {response.status_code}"
                )
                return None
        except Exception as e:
            self.log_test(f"GET /api/videos/{video_id}", False, f"Error: {str(e)}")
            return None

    def test_analyze_hook(self, video_id):
        """Test POST /api/videos/{video_id}/analyze-hook - may take 15-40s"""
        try:
            print(f"\n⏳ Analyzing hook for video {video_id} (may take 15-40s)...")
            response = requests.post(
                f"{self.base_url}/videos/{video_id}/analyze-hook",
                timeout=60
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = [
                    "id", "video_id", "frames", "facial_expressions",
                    "body_language_gestures", "pacing_cuts", "text_overlays_timing",
                    "audio_cues_inferred", "hook_summary", "effectiveness_score",
                    "key_hook_frame_index", "replicable_mechanics"
                ]
                has_all_fields = all(field in data for field in required_fields)
                has_frames = len(data.get("frames", [])) > 0
                score_valid = 1 <= data.get("effectiveness_score", 0) <= 10
                
                success = has_all_fields and has_frames and score_valid
                
                self.log_test(
                    f"POST /api/videos/{video_id}/analyze-hook",
                    success,
                    f"Analysis complete, Score: {data.get('effectiveness_score')}/10, Frames: {len(data.get('frames', []))}, All fields present: {has_all_fields}",
                    {
                        "analysis_id": data.get("id"),
                        "effectiveness_score": data.get("effectiveness_score"),
                        "frame_count": len(data.get("frames", [])),
                        "hook_summary": data.get("hook_summary", "")[:100]
                    }
                )
                return data if success else None
            else:
                error_msg = response.text[:200] if response.text else "No error message"
                self.log_test(
                    f"POST /api/videos/{video_id}/analyze-hook",
                    False,
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
                return None
        except Exception as e:
            self.log_test(f"POST /api/videos/{video_id}/analyze-hook", False, f"Error: {str(e)}")
            return None

    def test_get_analysis(self, video_id):
        """Test GET /api/videos/{video_id}/analysis"""
        try:
            response = requests.get(f"{self.base_url}/videos/{video_id}/analysis", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    f"GET /api/videos/{video_id}/analysis",
                    True,
                    f"Analysis retrieved, Score: {data.get('effectiveness_score')}/10",
                    data
                )
                return data
            else:
                self.log_test(
                    f"GET /api/videos/{video_id}/analysis",
                    False,
                    f"Status: {response.status_code}"
                )
                return None
        except Exception as e:
            self.log_test(f"GET /api/videos/{video_id}/analysis", False, f"Error: {str(e)}")
            return None

    def test_customize(self, video_id, photo_path, mode="preserve", frame_indices=None):
        """Test POST /api/videos/{video_id}/customize - may take 10-20s per frame"""
        try:
            frame_count = len(frame_indices) if frame_indices else 1
            print(f"\n⏳ Generating {frame_count} customized preview(s) for video {video_id} in {mode} mode (may take {frame_count * 10}-{frame_count * 20}s)...")
            
            # Create a simple test image if photo_path doesn't exist
            if not Path(photo_path).exists():
                from PIL import Image
                img = Image.new('RGB', (400, 400), color=(73, 109, 137))
                Path(photo_path).parent.mkdir(parents=True, exist_ok=True)
                img.save(photo_path)
            
            with open(photo_path, 'rb') as f:
                files = {'person_photo': ('test_photo.jpg', f, 'image/jpeg')}
                data = {
                    'mode': mode,
                }
                
                if frame_indices:
                    data['frame_indices'] = json.dumps(frame_indices)
                
                if mode == 'custom':
                    data.update({
                        'environment': 'Cozy bedroom',
                        'background': 'Warm afternoon light',
                        'clothing': 'Casual streetwear',
                        'custom_instructions': 'Test customization'
                    })
                
                response = requests.post(
                    f"{self.base_url}/videos/{video_id}/customize",
                    files=files,
                    data=data,
                    timeout=120
                )
            
            success = response.status_code == 200
            
            if success:
                result = response.json()
                has_required = all(
                    field in result for field in [
                        "id", "video_id", "generated_images",
                        "generation_spec", "mode"
                    ]
                )
                
                generated_count = len(result.get("generated_images", []))
                expected_count = len(frame_indices) if frame_indices else 1
                
                self.log_test(
                    f"POST /api/videos/{video_id}/customize (mode={mode}, frames={frame_count})",
                    has_required and generated_count == expected_count,
                    f"Customization complete, ID: {result.get('id')}, Mode: {result.get('mode')}, Generated images: {generated_count}/{expected_count}",
                    {
                        "customization_id": result.get("id"),
                        "mode": result.get("mode"),
                        "generated_images_count": generated_count,
                        "has_generation_spec": "generation_spec" in result
                    }
                )
                return result if has_required else None
            else:
                error_msg = response.text[:200] if response.text else "No error message"
                self.log_test(
                    f"POST /api/videos/{video_id}/customize (mode={mode}, frames={frame_count})",
                    False,
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
                return None
        except Exception as e:
            self.log_test(f"POST /api/videos/{video_id}/customize (mode={mode})", False, f"Error: {str(e)}")
            return None

    def test_get_customizations(self):
        """Test GET /api/customizations"""
        try:
            response = requests.get(f"{self.base_url}/customizations", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    "GET /api/customizations",
                    True,
                    f"Retrieved {len(data)} customizations",
                    {"count": len(data)}
                )
                return data
            else:
                self.log_test("GET /api/customizations", False, f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.log_test("GET /api/customizations", False, f"Error: {str(e)}")
            return []

    def test_generate_video_prompt(self, customization_id):
        """Test POST /api/customizations/{customization_id}/generate-video-prompt - may take 10-20s"""
        try:
            print(f"\n⏳ Generating video prompt for customization {customization_id} (may take 10-20s)...")
            response = requests.post(
                f"{self.base_url}/customizations/{customization_id}/generate-video-prompt",
                json={
                    "brand_name": "Test Brand",
                    "brand_goal": "Drive app installs",
                    "brand_details": "A revolutionary app that changes lives",
                    "duration_seconds": 30
                },
                timeout=60
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                required_fields = [
                    "id", "customization_id", "brand_name", "brand_goal",
                    "brand_details", "target_duration_seconds", "prompt_breakdown",
                    "full_prompt_text", "status"
                ]
                has_all_fields = all(field in data for field in required_fields)
                
                # Check prompt_breakdown has required keys
                breakdown = data.get("prompt_breakdown", {})
                breakdown_keys = [
                    "content", "camera_angle", "view_position", "character_behavior",
                    "scene_details", "brand_narrative", "full_video_prompt"
                ]
                has_breakdown = all(key in breakdown for key in breakdown_keys)
                
                success = has_all_fields and has_breakdown
                
                self.log_test(
                    f"POST /api/customizations/{customization_id}/generate-video-prompt",
                    success,
                    f"Video prompt generated, Job ID: {data.get('id')}, Status: {data.get('status')}, Has all fields: {has_all_fields}, Has breakdown: {has_breakdown}",
                    {
                        "job_id": data.get("id"),
                        "status": data.get("status"),
                        "target_duration": data.get("target_duration_seconds"),
                        "prompt_length": len(data.get("full_prompt_text", ""))
                    }
                )
                return data if success else None
            else:
                error_msg = response.text[:200] if response.text else "No error message"
                self.log_test(
                    f"POST /api/customizations/{customization_id}/generate-video-prompt",
                    False,
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
                return None
        except Exception as e:
            self.log_test(f"POST /api/customizations/{customization_id}/generate-video-prompt", False, f"Error: {str(e)}")
            return None

    def test_generate_video(self, job_id, image_ids, edited_prompt=None):
        """Test POST /api/video-jobs/{job_id}/generate-video"""
        try:
            print(f"\n⏳ Saving video brief for job {job_id}...")
            response = requests.post(
                f"{self.base_url}/video-jobs/{job_id}/generate-video",
                json={
                    "image_ids": image_ids,
                    "edited_prompt": edited_prompt,
                    "duration_seconds": 30
                },
                timeout=10
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                # Should have status "pending_provider_selection"
                is_pending = data.get("status") == "pending_provider_selection"
                has_prompt = "full_prompt_text" in data
                
                self.log_test(
                    f"POST /api/video-jobs/{job_id}/generate-video",
                    is_pending and has_prompt,
                    f"Video brief saved, Status: {data.get('status')}, Has prompt: {has_prompt}",
                    {
                        "job_id": data.get("id"),
                        "status": data.get("status"),
                        "has_prompt": has_prompt
                    }
                )
                return data if is_pending else None
            else:
                error_msg = response.text[:200] if response.text else "No error message"
                self.log_test(
                    f"POST /api/video-jobs/{job_id}/generate-video",
                    False,
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
                return None
        except Exception as e:
            self.log_test(f"POST /api/video-jobs/{job_id}/generate-video", False, f"Error: {str(e)}")
            return None

    def test_get_video_job(self, job_id):
        """Test GET /api/video-jobs/{job_id}"""
        try:
            response = requests.get(f"{self.base_url}/video-jobs/{job_id}", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    f"GET /api/video-jobs/{job_id}",
                    True,
                    f"Video job retrieved, Status: {data.get('status')}",
                    data
                )
                return data
            else:
                self.log_test(
                    f"GET /api/video-jobs/{job_id}",
                    False,
                    f"Status: {response.status_code}"
                )
                return None
        except Exception as e:
            self.log_test(f"GET /api/video-jobs/{job_id}", False, f"Error: {str(e)}")
            return None

    def test_get_customization_video_jobs(self, customization_id):
        """Test GET /api/customizations/{customization_id}/video-jobs"""
        try:
            response = requests.get(f"{self.base_url}/customizations/{customization_id}/video-jobs", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    f"GET /api/customizations/{customization_id}/video-jobs",
                    True,
                    f"Retrieved {len(data)} video jobs for customization",
                    {"count": len(data)}
                )
                return data
            else:
                self.log_test(
                    f"GET /api/customizations/{customization_id}/video-jobs",
                    False,
                    f"Status: {response.status_code}"
                )
                return []
        except Exception as e:
            self.log_test(f"GET /api/customizations/{customization_id}/video-jobs", False, f"Error: {str(e)}")
            return []

    def test_get_history(self):
        """Test GET /api/history"""
        try:
            response = requests.get(f"{self.base_url}/history", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test(
                    "GET /api/history",
                    True,
                    f"Retrieved {len(data)} history items",
                    {"count": len(data)}
                )
                return data
            else:
                self.log_test("GET /api/history", False, f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.log_test("GET /api/history", False, f"Error: {str(e)}")
            return []

    def test_invalid_tiktok_url(self):
        """Test error handling for invalid TikTok URL"""
        try:
            response = requests.post(
                f"{self.base_url}/videos/ingest",
                json={"tiktok_url": "https://invalid-url.com/video", "niche": "pets"},
                timeout=10
            )
            # Should return 400 error
            success = response.status_code == 400
            self.log_test(
                "POST /api/videos/ingest (invalid URL)",
                success,
                f"Correctly rejected invalid URL with status {response.status_code}"
            )
            return success
        except Exception as e:
            self.log_test("POST /api/videos/ingest (invalid URL)", False, f"Error: {str(e)}")
            return False

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print(f"📊 TEST SUMMARY")
        print("="*70)
        print(f"Total tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        print("="*70)
        
        return self.tests_passed == self.tests_run


def main():
    print("="*70)
    print("🚀 HookForge Backend API Testing (V2 with Video Generation)")
    print(f"Backend URL: {BASE_URL}")
    print("="*70)
    
    tester = HookForgeAPITester()
    
    # Test 1: Root endpoint
    tester.test_root_endpoint()
    
    # Test 2: Get niches (should return 10)
    niches = tester.test_get_niches()
    
    # Test 3: Get niche videos (may take up to 20s on first load)
    videos = []
    if niches:
        videos = tester.test_get_niche_videos("fitness")
    
    # Test 4: Invalid URL error handling
    tester.test_invalid_tiktok_url()
    
    # Test 5-16: Full workflow with a real TikTok URL
    # Using the suggested test URL from the review request
    test_url = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
    
    # Test 5: Ingest video
    video = tester.test_ingest_video(test_url)
    
    if video:
        video_id = video.get("id")
        
        # Test 6: Get video
        tester.test_get_video(video_id)
        
        # Test 7: Analyze hook (may take 15-40s) - only if not already analyzed
        if video.get("status") != "analyzed":
            analysis = tester.test_analyze_hook(video_id)
        else:
            print(f"\n✓ Video {video_id} already analyzed, skipping analysis step")
            analysis = tester.test_get_analysis(video_id)
        
        if analysis:
            # Test 8: Get analysis (if we just analyzed)
            if video.get("status") != "analyzed":
                tester.test_get_analysis(video_id)
            
            # Test 9: Customize in preserve mode with 1 frame (may take 10-20s)
            photo_path = "/tmp/test_photo.jpg"
            key_frame = analysis.get("key_hook_frame_index", 1)
            customization = tester.test_customize(video_id, photo_path, mode="preserve", frame_indices=[key_frame])
            
            if customization:
                customization_id = customization.get("id")
                
                # Test 10: Customize in custom mode with 2 frames (may take 20-40s)
                # Select 2 frames: key frame and 1 other
                frames = analysis.get("frames", [])
                if len(frames) >= 2:
                    frame_indices = [key_frame, min(key_frame + 2, len(frames))]
                    tester.test_customize(video_id, photo_path, mode="custom", frame_indices=frame_indices)
                
                # Test 11: Generate video prompt (may take 10-20s)
                video_job = tester.test_generate_video_prompt(customization_id)
                
                if video_job:
                    job_id = video_job.get("id")
                    image_ids = [img["id"] for img in customization.get("generated_images", [])]
                    
                    # Test 12: Get video job
                    tester.test_get_video_job(job_id)
                    
                    # Test 13: Generate video (save brief)
                    tester.test_generate_video(job_id, image_ids, edited_prompt=video_job.get("full_prompt_text"))
                    
                    # Test 14: Get customization video jobs
                    tester.test_get_customization_video_jobs(customization_id)
    
    # Test 15: Get customizations list
    tester.test_get_customizations()
    
    # Test 16: Get history
    tester.test_get_history()
    
    # Print summary
    all_passed = tester.print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
