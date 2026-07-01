"""
Static niche/category configuration for the curated trending-video feed.
Each niche maps to a small set of real, well-known public TikTok creator
handles. Their latest videos + REAL metadata (views/likes/comments/thumbnail)
are fetched live via yt-dlp - nothing here is mocked video content, only the
list of creators to look up is curated ahead of time (since the official
TikTok trending API integration is deferred).
"""

NICHES = [
    {
        "key": "fitness",
        "label": "Fitness",
        "icon": "Dumbbell",
        "description": "Workout routines, transformations, and training hacks",
        "creators": ["mattdoesfitness", "pamela_rf", "heather.robertson"],
    },
    {
        "key": "comedy",
        "label": "Comedy",
        "icon": "Laugh",
        "description": "Skits, reactions, and viral comedic bits",
        "creators": ["khaby.lame", "brittany_broski", "zachking"],
    },
    {
        "key": "beauty",
        "label": "Beauty",
        "icon": "Sparkles",
        "description": "Makeup, skincare, and beauty tutorials",
        "creators": ["hyram", "mikaylanogueira", "jamescharles"],
    },
    {
        "key": "food",
        "label": "Food",
        "icon": "UtensilsCrossed",
        "description": "Recipes, cooking hacks, and food reviews",
        "creators": ["gordonramsayofficial", "cookingwithshereen", "cookingwithlynja"],
    },
    {
        "key": "fashion",
        "label": "Fashion",
        "icon": "Shirt",
        "description": "Outfits, styling tips, and fashion hauls",
        "creators": ["addisonre", "wisdm8", "wolfiecindy"],
    },
    {
        "key": "tech",
        "label": "Tech / SaaS",
        "icon": "Cpu",
        "description": "Gadgets, apps, and tech reviews",
        "creators": ["mkbhd", "ijustine", "mrwhosetheboss"],
    },
    {
        "key": "pets",
        "label": "Pets",
        "icon": "PawPrint",
        "description": "Cute, funny, and heartwarming pet moments",
        "creators": ["scout2015", "thedodo", "loki_the_wolfdog"],
    },
    {
        "key": "travel",
        "label": "Travel",
        "icon": "Plane",
        "description": "Destinations, travel hacks, and adventures",
        "creators": ["doyoutravel", "hobopeeba", "kara_and_nate"],
    },
    {
        "key": "finance",
        "label": "Finance / Business",
        "icon": "TrendingUp",
        "description": "Money tips, business advice, and entrepreneurship",
        "creators": ["garyvee", "humphreytalks", "thebudgetmom"],
    },
    {
        "key": "education",
        "label": "Education / Lifehacks",
        "icon": "GraduationCap",
        "description": "Life hacks, facts, and quick learning",
        "creators": ["aliabdaal", "5.minute.crafts", "factsdaily"],
    },
]

NICHE_MAP = {n["key"]: n for n in NICHES}
