"""
test_processor.py
Quick validation test to verify that the drawtext overlay triggers in the last 3 seconds.
"""
import os
import logging
from pathlib import Path
from processor import ClipProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clipfarmer.test")

def run_local_test():
    logger.info("Testing local ClipProcessor modifications...")
    
    # Initialize processor using your config settings
    processor = ClipProcessor(config_path="config.json")
    
    # Scan for any available source video in your downloads folder
    download_dir = Path(processor.config["paths"]["downloads"])
    raw_videos = list(download_dir.glob("**/*.mp4")) + list(download_dir.glob("**/*.mkv"))
    
    if not raw_videos:
        logger.error("❌ No raw videos found in your downloads directory. Please download a file or let scheduler.py run briefly first.")
        return

    test_input = str(raw_videos[0])
    test_id = "TEST_CYCLE_01"
    
    logger.info(f"📁 Using video source: {test_input}")
    logger.info("⏳ Processing video filters (this may take a moment)...")
    
    # Run the core process function containing your updated FFmpeg filters
    output_file = processor.process(input_path=test_input, job_id=test_id)
    
    if output_file and os.path.exists(output_file):
        print("\n================== TEST SUCCESSFUL ✅ ==================")
        print(f"Rendered video created at: {output_file}")
        print("Action: Open this file and skip to the final 3 seconds to verify!")
        print("========================================================\n")
    else:
        logger.error("❌ Video processing failed. Check terminal for filter block errors.")

if __name__ == "__main__":
    run_local_test()
_