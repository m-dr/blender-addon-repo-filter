# Add-on Repository Filter for Blender

Filter installed add-ons in Blender Preferences by extension repository.

## Features

- **Filter by Extension Repository**: Filter your installed add-ons list in `Preferences > Add-ons` by any specific extension repository (e.g., `extensions.blender.org`, `User Default`, custom community repositories).
- **All Repositories / All Extensions / Legacy Add-ons**: Quickly switch between viewing all items, extensions-only, or legacy add-ons not managed by Blender's extension platform.
- **Dynamic Live Item Counts**: Displays the number of installed add-ons next to each repository name directly in the dropdown.
- **Dual Placement**: Integrated directly into the Add-ons header row next to the search box, as well as inside the Add-on Tags popover.
- **Native & Safe**: Integrates cleanly with Blender's native UI system without triggering false missing-module warnings or interfering with expand/collapse, preferences, or update checks.

## Compatibility

- Blender 5.2+ (LTS)
- Tested with Blender 5.2.3 LTS

## Installation

### As an Extension (Recommended)
1. In Blender, go to **Preferences > Get Extensions**.
2. If using a local repository or repository index, install `addon_repo_filter`.
3. Or install from disk via **Preferences > Get Extensions > ▾ (Menu) > Install from Disk...** selecting the `.zip` archive.

### Manual / Developer Installation
Link or copy this folder into your Blender extensions repository directory (e.g., `user_default` or `local_dev`).

## License

GPL-3.0-or-later
