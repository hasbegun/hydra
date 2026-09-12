#!/usr/bin/env python3
"""
Generate app icons for iOS, Android, macOS, Windows, and Linux
from the source hydra_logo.png
"""

import os
from PIL import Image

# Source logo
SOURCE_LOGO = "/Users/innox/projects/garak/hydra/frontend/hydra_logo.png"
FRONTEND_DIR = "/Users/innox/projects/garak/hydra/frontend"

# Icon sizes for different platforms
ICON_SIZES = {
    # iOS
    "ios": {
        "path": "ios/Runner/Assets.xcassets/AppIcon.appiconset",
        "sizes": [
            ("Icon-App-20x20@1x.png", 20),
            ("Icon-App-20x20@2x.png", 40),
            ("Icon-App-20x20@3x.png", 60),
            ("Icon-App-29x29@1x.png", 29),
            ("Icon-App-29x29@2x.png", 58),
            ("Icon-App-29x29@3x.png", 87),
            ("Icon-App-40x40@1x.png", 40),
            ("Icon-App-40x40@2x.png", 80),
            ("Icon-App-40x40@3x.png", 120),
            ("Icon-App-60x60@2x.png", 120),
            ("Icon-App-60x60@3x.png", 180),
            ("Icon-App-76x76@1x.png", 76),
            ("Icon-App-76x76@2x.png", 152),
            ("Icon-App-83.5x83.5@2x.png", 167),
            ("Icon-App-1024x1024@1x.png", 1024),
        ]
    },

    # Android
    "android": {
        "path": "android/app/src/main/res",
        "sizes": [
            ("mipmap-mdpi/ic_launcher.png", 48),
            ("mipmap-hdpi/ic_launcher.png", 72),
            ("mipmap-xhdpi/ic_launcher.png", 96),
            ("mipmap-xxhdpi/ic_launcher.png", 144),
            ("mipmap-xxxhdpi/ic_launcher.png", 192),
        ]
    },

    # macOS
    "macos": {
        "path": "macos/Runner/Assets.xcassets/AppIcon.appiconset",
        "sizes": [
            ("app_icon_16.png", 16),
            ("app_icon_32.png", 32),
            ("app_icon_64.png", 64),
            ("app_icon_128.png", 128),
            ("app_icon_256.png", 256),
            ("app_icon_512.png", 512),
            ("app_icon_1024.png", 1024),
        ]
    },

    # Windows
    "windows": {
        "path": "windows/runner/resources",
        "sizes": [
            ("app_icon.ico", [16, 32, 48, 64, 128, 256]),  # ICO contains multiple sizes
        ]
    },

    # Linux
    "linux": {
        "path": "linux",
        "sizes": [
            ("hydra_logo.png", 512),  # Main icon
        ]
    },

    # Web (Favicon)
    "web": {
        "path": "web",
        "sizes": [
            ("favicon.ico", [16, 32, 48]),  # Multi-size favicon
            ("icons/Icon-192.png", 192),  # PWA icon
            ("icons/Icon-512.png", 512),  # PWA icon
            ("icons/Icon-maskable-192.png", 192),  # Maskable icon
            ("icons/Icon-maskable-512.png", 512),  # Maskable icon
        ]
    }
}

def create_icon(source_img, size, output_path):
    """Create an icon of specified size from source image"""
    # Use LANCZOS for high-quality downsampling
    resized = source_img.resize((size, size), Image.Resampling.LANCZOS)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save the icon
    resized.save(output_path, "PNG")
    print(f"  ✅ Created {output_path} ({size}x{size})")

def create_ico(source_img, sizes, output_path):
    """Create Windows .ico file with multiple sizes"""
    icons = []
    for size in sizes:
        resized = source_img.resize((size, size), Image.Resampling.LANCZOS)
        icons.append(resized)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    icons[0].save(output_path, format='ICO', sizes=[(img.width, img.height) for img in icons])
    print(f"  ✅ Created {output_path} (multi-size ICO)")

def main():
    print("=" * 80)
    print("Generating App Icons for All Platforms")
    print("=" * 80)

    # Load source logo
    print(f"\n📷 Loading source logo: {SOURCE_LOGO}")
    try:
        source_img = Image.open(SOURCE_LOGO)
        print(f"   Original size: {source_img.size}")
    except Exception as e:
        print(f"❌ Error loading source logo: {e}")
        return 1

    # Convert to RGBA if needed
    if source_img.mode != 'RGBA':
        source_img = source_img.convert('RGBA')

    total_created = 0

    # Generate icons for each platform
    for platform, config in ICON_SIZES.items():
        print(f"\n{'='*80}")
        print(f"📱 {platform.upper()}")
        print(f"{'='*80}")

        base_path = os.path.join(FRONTEND_DIR, config["path"])

        for item in config["sizes"]:
            filename = item[0]
            size_or_sizes = item[1]
            output_path = os.path.join(base_path, filename)

            try:
                if isinstance(size_or_sizes, list):
                    # Windows ICO with multiple sizes
                    create_ico(source_img, size_or_sizes, output_path)
                else:
                    # Single size PNG
                    create_icon(source_img, size_or_sizes, output_path)
                total_created += 1
            except Exception as e:
                print(f"  ❌ Error creating {filename}: {e}")

    print(f"\n{'='*80}")
    print(f"✅ Successfully created {total_created} icon files across all platforms")
    print(f"{'='*80}")

    return 0

if __name__ == "__main__":
    exit(main())
