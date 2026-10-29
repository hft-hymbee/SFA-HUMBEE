// Regenerate every native app icon and launch-screen image, plus the web copies
// of the logo, from the master SVGs in /brand. Re-run after changing the logo,
// then rebuild the app.
//   Usage: pnpm --dir apps/mobile icons
import { copyFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const MOBILE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BRAND_DIR = path.resolve(MOBILE_DIR, "../../brand");
const IOS_ASSETS = path.join(MOBILE_DIR, "ios/App/App/Assets.xcassets");
const ANDROID_RES = path.join(MOBILE_DIR, "android/app/src/main/res");
const REPO_DIR = path.resolve(MOBILE_DIR, "../..");

const MARK = path.join(BRAND_DIR, "humbee-go-mark.svg");
const LOCKUP = path.join(BRAND_DIR, "humbee-go-lockup.svg");

const WHITE = { r: 255, g: 255, b: 255, alpha: 1 };
const CLEAR = { r: 0, g: 0, b: 0, alpha: 0 };

// Android launcher sizes per density: legacy icon, adaptive foreground layer.
const DENSITIES = { mdpi: [48, 108], hdpi: [72, 162], xhdpi: [96, 216], xxhdpi: [144, 324], xxxhdpi: [192, 432] };

function svg(file, resize) {
  return sharp(file, { density: 1200 }).resize(resize).png().toBuffer();
}

// Draws `layer` centred on a width x height canvas. Opaque output has its alpha
// channel removed, which App Store Connect requires for the iOS icon.
async function write(file, width, height, background, layer, mask) {
  let image = sharp({ create: { width, height, channels: 4, background } })
    .composite([...(layer ? [{ input: layer, gravity: "center" }] : []), ...(mask ? [{ input: mask, blend: "dest-in" }] : [])]);
  image = sharp(await image.png().toBuffer());
  if (background.alpha === 1 && !mask) image = image.removeAlpha();
  await image.png({ compressionLevel: 9 }).toFile(file);
  console.log(`  ${path.relative(MOBILE_DIR, file)}  ${width}x${height}`);
}

const circle = (size) =>
  Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}"/></svg>`);

// The splash is scaled to fill the screen, so size the lockup off the short edge.
async function splash(file, width, height, share) {
  const lockup = await svg(LOCKUP, { width: Math.round(Math.min(width, height) * share) });
  await write(file, width, height, WHITE, lockup);
}

// The web app and design system ship their own copies; keep them in step.
console.log("Web");
for (const [from, to] of [
  [LOCKUP, "packages/humbee-design-system/src/assets/humbee_go_logo.svg"],
  [MARK, "apps/web/app/icon.svg"],
]) {
  await copyFile(from, path.join(REPO_DIR, to));
  console.log(`  ${to}`);
}

console.log("iOS");
await write(path.join(IOS_ASSETS, "AppIcon.appiconset/AppIcon-512@2x.png"), 1024, 1024, WHITE, await svg(MARK, { height: 640 }));
for (const name of ["splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"]) {
  // LaunchScreen aspect-fills this square, so a phone only shows its middle ~46%.
  await splash(path.join(IOS_ASSETS, "Splash.imageset", name), 2732, 2732, 0.28);
}

console.log("Android");
for (const [density, [icon, foreground]] of Object.entries(DENSITIES)) {
  const dir = path.join(ANDROID_RES, `mipmap-${density}`);
  const mark = await svg(MARK, { height: Math.round(icon * 0.62) });
  await write(path.join(dir, "ic_launcher.png"), icon, icon, WHITE, mark);
  await write(path.join(dir, "ic_launcher_round.png"), icon, icon, WHITE, await svg(MARK, { height: Math.round(icon * 0.56) }), circle(icon));
  // Adaptive icons mask to the middle 66%; keep the mark inside that circle.
  await write(path.join(dir, "ic_launcher_foreground.png"), foreground, foreground, CLEAR, await svg(MARK, { height: Math.round(foreground * 0.46) }));
}
for (const dir of (await readdir(ANDROID_RES)).filter((d) => /^drawable(-(port|land)-\w+)?$/.test(d))) {
  const file = path.join(ANDROID_RES, dir, "splash.png");
  const { width, height } = await sharp(file).metadata();
  await splash(file, width, height, 0.55);
}
