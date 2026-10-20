# Using cutris

## Process a batch

1. Browse or drop **1–50 images**. Filenames sort naturally (`page2` before `page10`); use the queue arrows to change the order.
2. Choose **Maximum detail** or **Faster**. Use **Any background / AI only** for general images, or **White illustration** for extra cleanup on white backgrounds.
3. Select **Remove backgrounds**. Images run one at a time to limit memory use. The first image also includes model loading time.
4. Review each result, save any touch-ups, then download a PNG or the ordered batch ZIP.

**White illustration** refines the AI silhouette and reduces white contamination around its edges. If the border is not consistently white, it falls back to AI-only removal. **Any background / AI only** keeps the model's soft mask without white-edge refinement.

Pause finishes the current image before stopping. **Previous batches** reopens saved jobs. After an interrupted session, unfinished work is paused and can be resumed. Retry reprocesses failed items when a valid source was saved.

## Inspect and repair

Preview backgrounds help you inspect edges; they are not included in transparent exports. Switch between the original and cutout to check missing details.

| Control | Use |
| --- | --- |
| **Erase** | Paint away unwanted pixels. |
| **Restore** | Paint pixels back from the original. Painting beyond the subject also restores its background. |
| **Magic wand** | Preview a connected area of similar color, adjust tolerance, then choose **Erase selected area**. |
| **Undo / Redo** | Step through edits. `Ctrl+Z` undoes; `Ctrl+Shift+Z` redoes. |
| **Save touch-up** | Save the current edits before leaving or exporting the image. |
| **Reset touch-ups** | Return to the automatic cutout after confirmation, without rerunning the model. |

Magic wand selections appear pink until applied. Transparent pixels act as barriers, but connected subject details of similar color can also be selected. Inspect before erasing. `Esc` or **Clear selection** cancels the preview.

Brush size is **1–500 original-image pixels**, regardless of zoom. Pending edits remain in the current window until saved. Undo and redo history remains available while that image stays open.

On desktop and laptop windows, the preview adapts to the available height so editing and export controls stay visible. The image queue scrolls separately. Expand **Review notes** for edge checks and processing details. Narrow windows use a single-column layout.

## Crop and resize

Open **Crop & resize** on a finished cutout. Save pending touch-ups first.

**Download PNG** automatically trims empty transparent margins when you have not applied crop or resize settings. It uses the saved touch-ups and keeps even faint, partly transparent edges. To keep the full canvas, choose **Use full image**, turn off resizing, and **Apply changes**. Saved geometry takes precedence over the automatic download trim.

- **Auto crop** is selected for a new crop and detects unused transparent margins immediately. It keeps soft, partly transparent edges. Opaque areas are kept even if their color matches the background.
- Dragging the crop box, entering crop dimensions, or changing resizing switches to **Manual crop**. You can also select Manual crop to draw a new selection.
- **Resize output** sets the final width and height. Leave **Keep proportions** checked to preserve the subject's shape.
- Review the preview, then **Apply changes** to save. **Cancel** leaves the saved image unchanged.

Cropping and resizing affect the PNG and batch ZIP. The original stays intact, and later touch-ups use the full source image. Reopen **Crop & resize** to adjust the saved canvas; custom crops and resizing reopen in Manual mode with their saved values. **Use full image** removes the crop; **Reset size** removes resizing. Auto crop uses the current cutout; run it again after touch-ups if you want new bounds.

## Move around the image

- Drag to pan; use the wheel to zoom around the cursor.
- While an editing tool is active, right-drag, middle-drag, or `Space`-drag pans without painting.
- Click the active tool again, or **Done editing**, to leave it.
- Turn off **Wheel zoom** to scroll the page over the preview. `Ctrl` + wheel still zooms.
- **Fit** recenters the image. Zoom supports **5%–800%**, including 100% for pixel inspection.

## Formats and exports

| | Supported |
| --- | --- |
| Input | Single-frame PNG, JPG, WebP, BMP, TIFF |
| Limits per image | 30 MB, 24 million pixels, 12,000 pixels per side |
| PNG download | sRGB RGBA PNG, auto cropped by default or using your saved crop and resize settings |
| Batch export | Ordered ZIP using saved image dimensions, with a manifest of settings and failures |

Animated files and multi-page TIFFs are rejected. EXIF orientation is honored; ICC-tagged inputs are converted to sRGB when possible. Exports omit DPI and EXIF metadata. Set print size in your layout application.

Export names use `001_original-name.png`, `002_original-name.png`, and so on. Source files are never overwritten. Preview colors are never flattened into the PNG.

Existing transparency is preserved instead of re-segmented. This protects an alpha channel but leaves any opaque background patches for manual correction. Process a flattened copy if you want AI removal again.

## What to expect

The model predicts a mask at **1024 × 1024**, then resizes and refines it against the source. Original-dimension output does not guarantee perfect segmentation. Hair, glass, shadows, white-on-white edges, translucent details, and detached objects may need touch-ups.

Images, automatic results, and saved edits stay on your computer. Saved batches use disk space until removed. See [privacy and storage](privacy.md) or [Windows troubleshooting](windows.md).
