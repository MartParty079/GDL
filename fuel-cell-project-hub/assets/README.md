# App icon

Final assets: app_icon.png (PNG master) and app_icon.ico (Windows frames at
16, 24, 32, 48, 64, 128 and 256 pixels). Created with the built-in imagegen tool;
Windows frames were exported with tools/build_icon.py using Qt. No client/API
key was needed. The PNG is deliberately opaque for clean small-size edges.

Final generation prompt:

> Use case: logo-brand. Final PNG master for a professional Fuel Cell Project Hub Windows desktop app icon. OPAQUE IMAGE, no transparency or alpha cutout. Entire square canvas filled with a uniform very pale cool gray #F3F6FA. Center a rounded-square soft ice-blue tile occupying 92% of the square, smooth crisp edges. Inside tile, simple three-layer stacked fuel-cell symbol, matte blue/cyan/blue, thick minimal geometry, small clean white energy droplet mark on top. Apple-inspired polished minimal utility icon, softer flat shading, clean neutral appearance, readable at 16px. Comfortable margins, no text, no watermarks, no speckles, no particles, no exterior noise, no neon, no glow. Actual square app image, not a mockup or device screenshot.

The resource resolver, QApplication, HubWindow and PyInstaller spec use these
assets without any personal absolute path. Future installer and shortcuts should
reference the same ICO. There is currently no About dialog or installer.
