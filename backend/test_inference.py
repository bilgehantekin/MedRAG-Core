"""
Test script for TorchXRayVision inference
Run this to verify the official preprocessing pipeline works
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_inference():
    print("=" * 50)
    print("Testing TorchXRayVision Official Pipeline")
    print("=" * 50)

    # Step 1: Test imports
    print("\n[1/4] Testing imports...")
    try:
        import torch
        import torchxrayvision as xrv
        import torchvision
        from PIL import Image
        print(f"  ✓ torch version: {torch.__version__}")
        print(f"  ✓ torchxrayvision imported")
        print(f"  ✓ torchvision version: {torchvision.__version__}")
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False

    # Step 2: Test model loading
    print("\n[2/4] Testing model loading...")
    try:
        from app.image.inference import load_model, is_model_loaded

        if not is_model_loaded():
            success = load_model()
            if success:
                print("  ✓ Model loaded successfully")
            else:
                print("  ✗ Model loading returned False")
                return False
        else:
            print("  ✓ Model already loaded")
    except Exception as e:
        print(f"  ✗ Model loading failed: {e}")
        return False

    # Step 3: Test preprocessing
    print("\n[3/4] Testing preprocessing...")
    try:
        from app.image.inference import preprocess_image

        # Create a dummy test image
        test_img = Image.new('RGB', (512, 512), color=(128, 128, 128))

        tensor = preprocess_image(test_img)
        print(f"  ✓ Preprocessed tensor shape: {tensor.shape}")
        print(f"  ✓ Expected shape: (1, 1, 224, 224)")

        if tensor.shape == (1, 1, 224, 224):
            print("  ✓ Shape is correct!")
        else:
            print(f"  ✗ Unexpected shape")
            return False
    except Exception as e:
        print(f"  ✗ Preprocessing failed: {e}")
        return False

    # Step 4: Test prediction
    print("\n[4/4] Testing prediction...")
    try:
        from app.image.inference import predict

        result = predict(test_img)

        print(f"  ✓ Got predictions for {len(result['pathologies'])} pathologies")
        print(f"  ✓ Pathologies: {result['pathologies'][:5]}...")

        # Show top 3 scores
        scores = result['raw_scores']
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        print("\n  Top 3 predictions (raw scores):")
        for label, score in sorted_scores:
            print(f"    - {label}: {score:.4f}")

    except Exception as e:
        print(f"  ✗ Prediction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)
    return True


def test_with_real_image(image_path: str):
    """Test with a real X-ray image"""
    print(f"\nTesting with real image: {image_path}")

    from PIL import Image
    from app.image.inference import predict, is_model_loaded, load_model

    if not is_model_loaded():
        load_model()

    img = Image.open(image_path)
    print(f"Image size: {img.size}")

    result = predict(img)

    # Apply sigmoid and sort
    import math
    predictions = []
    for label, score in result['raw_scores'].items():
        prob = 1 / (1 + math.exp(-score))
        predictions.append((label, prob))

    predictions.sort(key=lambda x: x[1], reverse=True)

    print("\nTop 5 predictions:")
    for label, prob in predictions[:5]:
        status = "⚠️" if prob >= 0.5 else "  "
        print(f"  {status} {label}: {prob*100:.1f}%")


if __name__ == "__main__":
    success = test_inference()

    if success and len(sys.argv) > 1:
        # Test with real image if provided
        test_with_real_image(sys.argv[1])
    elif success:
        print("\nTo test with a real X-ray image:")
        print("  python test_inference.py /path/to/xray.jpg")
