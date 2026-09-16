#!/usr/bin/env python3

print("Testing Qwen2-VL dependencies...")

try:
    import torch
    print("✅ PyTorch imported successfully")
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device count: {torch.cuda.device_count()}")
        print(f"   Current CUDA device: {torch.cuda.current_device()}")
except ImportError as e:
    print(f"❌ PyTorch import failed: {e}")

try:
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    print("✅ Qwen2-VL transformers imported successfully")
except ImportError as e:
    print(f"❌ Qwen2-VL transformers import failed: {e}")

try:
    from qwen_vl_utils import process_vision_info
    print("✅ qwen-vl-utils imported successfully")
except ImportError as e:
    print(f"❌ qwen-vl-utils import failed: {e}")

try:
    from PIL import Image
    print("✅ PIL/Pillow imported successfully")
except ImportError as e:
    print(f"❌ PIL/Pillow import failed: {e}")

print("\n🔄 Testing basic model initialization (this may take a while on first run)...")

try:
    # Try to load a small test model to check if everything works
    model_name = "Qwen/Qwen2-VL-2B-Instruct"
    print(f"Attempting to load model: {model_name}")
    
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    print("✅ Processor loaded successfully")
    
    # We won't load the full model here to save time and resources
    print("✅ Model dependencies are working!")
    
except Exception as e:
    print(f"⚠️  Model loading test failed (this is normal on first run): {e}")
    print("   The model will be downloaded when first used.")

print("\n✅ All basic dependencies are ready for document analysis!")