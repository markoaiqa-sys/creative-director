import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import Settings
from app.models import InstagramDirectReelRequest
from app.services.engine import ServiceContainer

async def run_test():
    settings = Settings()
    print("Initializing ServiceContainer...")
    container = ServiceContainer(settings)
    
    print("ServiceContainer initialized.")
    print(f"Groq API Key configured: {bool(settings.groq_api_key)}")
    print(f"Gemini API Key configured: {bool(settings.gemini_api_key)}")
    
    request = InstagramDirectReelRequest(
        brief="A funny 30-second comedy reel about a developer trying to fix a bug in production at 5 PM on a Friday.",
        brand_name="BugTracker Pro",
        niche="software-engineering",
        audience="developers and software engineers",
        creator_persona="stressed coder",
        goal="engagement and shares",
        tone="humorous and relatable",
    )
    
    print("Invoking direct_reel on InstagramDirectorEngine...")
    try:
        # Call direct_reel as normal
        response = await container.instagram_engine.direct_reel(request)
        print("\nSuccess! Response received.")
        print(f"Title: {response.title}")
        print(f"Viral Probability Score: {response.viral_probability_score}")
        print(f"Audience Retention Prediction: {response.audience_retention_prediction}")
        print("\nSpoken Script:")
        print(response.script.spoken_script)
        
        print("\nTimeline Beat Count:", len(response.second_by_second_timeline))
        if response.second_by_second_timeline:
            for idx, beat in enumerate(response.second_by_second_timeline[:3], 1):
                print(f"  Beat {idx} ({beat.second_range}): {beat.scene[:60]}...")
                print(f"    Camera: {beat.camera_direction}")
                print(f"    Emotional Intent: {beat.emotional_intent}")
                print(f"    Retention Note: {beat.retention_note}")
                
        print("\nDirector Notes:")
        for note in response.director_notes:
            print(f"  - {note}")
            
    except Exception as e:
        print("\nError encountered:", type(e).__name__, str(e))
        import traceback
        traceback.print_exc()
    finally:
        await container.aclose()

if __name__ == "__main__":
    asyncio.run(run_test())
