bl_info = {
    "name": "Add-on Repository Filter (DEV)",
    "author": "MD <m-dr>",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "Preferences > Add-ons",
    "description": "Filter installed add-ons in preferences by extension repository",
    "category": "System",
}

import bpy
import addon_utils
from bpy.props import EnumProperty

# Storage for original Blender functions so they can be perfectly restored on unregister
_orig_addons_panel_draw = None
_orig_addons_panel_draw_items = None


def get_addon_repo_items(self, context):
    """Dynamically populate repository filter items with counts of installed add-ons."""
    if context is None or not hasattr(context, "preferences"):
        return [
            ('_ALL_', "All Repositories", "Show all add-ons and extensions", 'RESTRICT_VIEW_OFF', 0),
            ('_EXTENSIONS_', "All Extensions", "Show all extensions", 'PACKAGE', 1),
            ('_LEGACY_', "Legacy Add-ons", "Show legacy add-ons", 'SCRIPTPLUGINS', 2),
        ]

    mods = addon_utils.modules(refresh=False)
    repo_counts = {}
    legacy_count = 0
    ext_total = 0

    for mod in mods:
        m_name = getattr(mod, "__name__", "")
        if addon_utils.check_extension(m_name):
            ext_total += 1
            parts = m_name.split(".")
            if len(parts) >= 2:
                r_id = parts[1]
                repo_counts[r_id] = repo_counts.get(r_id, 0) + 1
        else:
            legacy_count += 1

    items = [
        ('_ALL_', f"All Repositories ({len(mods)})", "Show all add-ons and extensions", 'RESTRICT_VIEW_OFF', 0),
        ('_EXTENSIONS_', f"All Extensions ({ext_total})", "Show all extensions from all repositories", 'PACKAGE', 1),
        ('_LEGACY_', f"Legacy Add-ons ({legacy_count})", "Show legacy add-ons not installed as extensions", 'SCRIPTPLUGINS', 2),
    ]

    repos = getattr(context.preferences.extensions, "repos", []) if hasattr(context.preferences, "extensions") else []
    for idx, repo in enumerate(repos, start=3):
        if not repo.enabled:
            continue
        cnt = repo_counts.get(repo.module, 0)
        items.append((
            repo.module,
            f"{repo.name} ({cnt})",
            f"Only show extensions installed from repository '{repo.name}' ({repo.module})",
            'URL' if repo.use_remote_url else 'FILE_FOLDER',
            idx
        ))

    return items


def filtered_addons_panel_draw_items(
    layout,
    context,
    *,
    addon_modules,
    used_addon_module_name_map,
    search_casefold,
    addon_tags_exclude,
    enabled_only,
    addon_extension_manifest_map,
    addon_extension_block_map,
    show_development,
    show_developer_ui,
):
    """
    Wrap addons_panel_draw_items to filter add-ons by extension repository while
    returning all discovered module names so Blender's missing_modules check is satisfied.
    """
    global _orig_addons_panel_draw_items

    all_modules = list(addon_modules)
    all_module_names = {getattr(m, "__name__", "") for m in all_modules}

    wm = context.window_manager
    repo_filter = getattr(wm, "addon_repo_filter", "_ALL_")

    if repo_filter == "_ALL_":
        filtered_modules = all_modules
    elif repo_filter == "_LEGACY_":
        filtered_modules = [m for m in all_modules if not addon_utils.check_extension(m.__name__)]
    elif repo_filter == "_EXTENSIONS_":
        filtered_modules = [m for m in all_modules if addon_utils.check_extension(m.__name__)]
    else:
        # Filter for a specific repository module name (e.g. 'blender_org', 'user_default')
        filtered_modules = []
        for m in all_modules:
            m_name = m.__name__
            if addon_utils.check_extension(m_name):
                parts = m_name.split(".")
                if len(parts) >= 2 and parts[1] == repo_filter:
                    filtered_modules.append(m)

    if _orig_addons_panel_draw_items is not None:
        _orig_addons_panel_draw_items(
            layout,
            context,
            addon_modules=filtered_modules,
            used_addon_module_name_map=used_addon_module_name_map,
            search_casefold=search_casefold,
            addon_tags_exclude=addon_tags_exclude,
            enabled_only=enabled_only,
            addon_extension_manifest_map=addon_extension_manifest_map,
            addon_extension_block_map=addon_extension_block_map,
            show_development=show_development,
            show_developer_ui=show_developer_ui,
        )

    if repo_filter != "_ALL_" and not filtered_modules:
        box = layout.box()
        box.label(text="No add-ons installed from this repository.", icon='INFO')

    # Return all_module_names so Blender does not falsely report missing add-ons
    return all_module_names


def filtered_addons_panel_draw(panel, context):
    """Replacement for bl_pkg.bl_extension_ui.addons_panel_draw with repository filter UI."""
    import bl_pkg.bl_extension_ui as ext_ui

    prefs = context.preferences
    view = prefs.view
    wm = context.window_manager
    layout = panel.layout

    split = layout.split(factor=0.45)
    row_a = split.row()
    row_b = split.row(align=True)

    row_a.prop(wm, "addon_search", text="", icon='VIEWZOOM', placeholder="Search Add-ons")

    # Repository Filter Dropdown
    row_b.prop(wm, "addon_repo_filter", text="")
    row_b.separator()

    row_b.prop(view, "show_addons_enabled_only", text="Enabled Only")

    rowsub = row_b.row(align=True)
    rowsub.popover("USERPREF_PT_addons_tags", text="", icon='TAG')
    rowsub.separator()
    rowsub.menu("USERPREF_MT_addons_settings", text="", icon='DOWNARROW_HLT')
    del split, row_a, row_b, rowsub

    addon_tags_exclude = ext_ui.tags_exclude_get(wm, "addon_tags")

    ext_ui.addons_panel_draw_impl(
        panel,
        context,
        wm.addon_search.casefold(),
        addon_tags_exclude,
        view.show_addons_enabled_only,
        show_development=prefs.experimental.use_extensions_debug,
        show_developer_ui=prefs.view.show_developer_ui,
    )


def addons_tags_draw(self, context):
    """Add repository selector to the top of the Add-on Tags popover."""
    layout = self.layout
    layout.label(text="Filter by Repository:")
    layout.prop(context.window_manager, "addon_repo_filter", text="")
    layout.separator()


classes = ()


def register():
    global _orig_addons_panel_draw, _orig_addons_panel_draw_items

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.addon_repo_filter = EnumProperty(
        name="Repository",
        description="Filter add-ons by extension repository or legacy status",
        items=get_addon_repo_items,
        default=0,
    )

    try:
        import bl_pkg.bl_extension_ui as ext_ui
        from bl_ui.space_userpref import USERPREF_PT_addons

        _orig_addons_panel_draw = ext_ui.addons_panel_draw
        _orig_addons_panel_draw_items = ext_ui.addons_panel_draw_items

        # Monkey-patch addons_panel_draw_items to support repo filtering
        ext_ui.addons_panel_draw_items = filtered_addons_panel_draw_items

        # Replace addons_panel_draw in USERPREF_PT_addons
        if hasattr(USERPREF_PT_addons, "remove") and _orig_addons_panel_draw in getattr(USERPREF_PT_addons.draw, "_draw_funcs", []):
            USERPREF_PT_addons.remove(_orig_addons_panel_draw)
        USERPREF_PT_addons.append(filtered_addons_panel_draw)

        # Prepend repository selector to tags popover
        if hasattr(ext_ui, "USERPREF_PT_addons_tags"):
            ext_ui.USERPREF_PT_addons_tags.prepend(addons_tags_draw)

    except Exception as e:
        print(f"[addon_repo_filter] Failed to attach UI hooks: {e}")


def unregister():
    global _orig_addons_panel_draw, _orig_addons_panel_draw_items

    try:
        import bl_pkg.bl_extension_ui as ext_ui
        from bl_ui.space_userpref import USERPREF_PT_addons

        # Remove custom draw function and restore original
        if hasattr(USERPREF_PT_addons, "remove"):
            if filtered_addons_panel_draw in getattr(USERPREF_PT_addons.draw, "_draw_funcs", []):
                USERPREF_PT_addons.remove(filtered_addons_panel_draw)
            if _orig_addons_panel_draw is not None and _orig_addons_panel_draw not in getattr(USERPREF_PT_addons.draw, "_draw_funcs", []):
                USERPREF_PT_addons.append(_orig_addons_panel_draw)

        # Restore original addons_panel_draw_items
        if _orig_addons_panel_draw_items is not None:
            ext_ui.addons_panel_draw_items = _orig_addons_panel_draw_items

        # Remove from tags popover
        if hasattr(ext_ui, "USERPREF_PT_addons_tags"):
            ext_ui.USERPREF_PT_addons_tags.remove(addons_tags_draw)

    except Exception as e:
        print(f"[addon_repo_filter] Failed to restore original hooks: {e}")

    if hasattr(bpy.types.WindowManager, "addon_repo_filter"):
        del bpy.types.WindowManager.addon_repo_filter

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
