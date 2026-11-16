bl_info = {
    "name": "Add-on Repository Filter (DEV)",
    "author": "MD <m-dr>",
    "version": (0, 1, 2),
    "blender": (5, 2, 0),
    "location": "Preferences > Add-ons",
    "description": "Filter installed add-ons in preferences by extension repository",
    "category": "System",
}

import traceback

import bpy
import addon_utils
from bpy.props import EnumProperty

# Storage for original Blender functions so they can be perfectly restored on unregister
_orig_addons_panel_draw = None
_orig_addons_panel_draw_items = None

# UI hook maintenance state.
_REGISTERED = False
_HEAL_INTERVAL = 1.0
_OUR_MODULE = __name__


def _log(message):
    print("[addon_repo_filter] " + message)


def _fn_name(func):
    return getattr(func, "__name__", "")


def _is_our_func(func, name):
    return _fn_name(func) == name and getattr(func, "__module__", "") == _OUR_MODULE


def get_addon_repo_items(self, context):
    """Dynamically populate repository filter items with counts of installed add-ons."""
    fallback = [
        ('_ALL_', "All Repositories", "Show all add-ons and extensions", 'RESTRICT_VIEW_OFF', 0),
        ('_EXTENSIONS_', "All Extensions", "Show all extensions", 'PACKAGE', 1),
        ('_LEGACY_', "Legacy Add-ons", "Show legacy add-ons", 'SCRIPTPLUGINS', 2),
    ]
    if context is None or not hasattr(context, "preferences"):
        return fallback

    try:
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
    except Exception:
        # A dynamic enum callback must never raise: Blender calls it while drawing.
        traceback.print_exc()
        return fallback


def _filtered_addons_panel_draw_items_impl(
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


def filtered_addons_panel_draw_items(layout, context, *args, **kwargs):
    """Fault-tolerant wrapper: never let filtering break Blender's add-on list."""
    try:
        return _filtered_addons_panel_draw_items_impl(layout, context, *args, **kwargs)
    except Exception:
        traceback.print_exc()
        if _orig_addons_panel_draw_items is not None:
            try:
                return _orig_addons_panel_draw_items(layout, context, *args, **kwargs)
            except Exception:
                traceback.print_exc()
        return set()


def _filtered_addons_panel_draw_impl(panel, context):
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


def filtered_addons_panel_draw(panel, context):
    """Hook for USERPREF_PT_addons: a failure must never hide the whole page."""
    try:
        _filtered_addons_panel_draw_impl(panel, context)
    except Exception:
        traceback.print_exc()
        if _orig_addons_panel_draw is not None:
            try:
                _orig_addons_panel_draw(panel, context)
            except Exception:
                traceback.print_exc()


def addons_tags_draw(self, context):
    """Add repository selector to the top of the Add-on Tags popover."""
    try:
        layout = self.layout
        layout.label(text="Filter by Repository:")
        layout.prop(context.window_manager, "addon_repo_filter", text="")
        layout.separator()
    except Exception:
        traceback.print_exc()


def _ensure_properties():
    if not hasattr(bpy.types.WindowManager, "addon_repo_filter"):
        bpy.types.WindowManager.addon_repo_filter = EnumProperty(
            name="Repository",
            description="Filter add-ons by extension repository or legacy status",
            items=get_addon_repo_items,
            default=0,
        )


def _capture_originals():
    global _orig_addons_panel_draw, _orig_addons_panel_draw_items
    try:
        import bl_pkg.bl_extension_ui as ext_ui
    except Exception:
        traceback.print_exc()
        return

    current_items = getattr(ext_ui, "addons_panel_draw_items", None)
    if current_items is not None and not _is_our_func(current_items, "filtered_addons_panel_draw_items"):
        _orig_addons_panel_draw_items = current_items

    if _orig_addons_panel_draw is None:
        _orig_addons_panel_draw = getattr(ext_ui, "addons_panel_draw", None)


def _install_hooks():
    """Install the UI hooks idempotently and in a stable order.

    Blender owns the panel draw-function list and can rebuild (dropping our
    function) or re-run registration (duplicating it) during a long session.
    Always reduce the list to exactly: [Blender's panel header draw, our draw].
    """
    _capture_originals()

    from bl_ui.space_userpref import USERPREF_PT_addons
    import bl_pkg.bl_extension_ui as ext_ui

    try:
        draw_funcs = USERPREF_PT_addons._dyn_ui_initialize()
    except Exception:
        traceback.print_exc()
        draw_funcs = getattr(getattr(USERPREF_PT_addons, "draw", None), "_draw_funcs", None)

    if draw_funcs is not None:
        for func in list(draw_funcs):
            name = _fn_name(func)
            module = getattr(func, "__module__", "")
            if module == _OUR_MODULE and name in {"filtered_addons_panel_draw", "filtered_addons_panel_draw_items"}:
                draw_funcs.remove(func)
            elif module == "bl_pkg.bl_extension_ui" and name in {"addons_panel_draw", "addons_panel_draw_impl"}:
                draw_funcs.remove(func)
        draw_funcs.append(filtered_addons_panel_draw)

    if getattr(ext_ui, "addons_panel_draw_items", None) is not filtered_addons_panel_draw_items:
        ext_ui.addons_panel_draw_items = filtered_addons_panel_draw_items

    tags_panel = getattr(ext_ui, "USERPREF_PT_addons_tags", None)
    if tags_panel is not None:
        try:
            tags_panel._dyn_ui_initialize()
            tag_funcs = getattr(getattr(tags_panel, "draw", None), "_draw_funcs", None)
            if tag_funcs is not None:
                for func in list(tag_funcs):
                    if _is_our_func(func, "addons_tags_draw"):
                        tag_funcs.remove(func)
        except Exception:
            traceback.print_exc()
        try:
            tags_panel.prepend(addons_tags_draw)
        except Exception:
            traceback.print_exc()

    _ensure_properties()


def _hooks_need_repair():
    try:
        from bl_ui.space_userpref import USERPREF_PT_addons
        import bl_pkg.bl_extension_ui as ext_ui

        draw_funcs = getattr(getattr(USERPREF_PT_addons, "draw", None), "_draw_funcs", None)
        if not draw_funcs:
            return True

        ours = [f for f in draw_funcs if _is_our_func(f, "filtered_addons_panel_draw")]
        if len(ours) != 1:
            return True

        for func in draw_funcs:
            if (getattr(func, "__module__", "") == "bl_pkg.bl_extension_ui"
                    and _fn_name(func) == "addons_panel_draw"):
                # Blender's own panel draw is back: our replacement must not stack on it.
                return True

        if getattr(ext_ui, "addons_panel_draw_items", None) is not filtered_addons_panel_draw_items:
            return True

        if not hasattr(bpy.types.WindowManager, "addon_repo_filter"):
            return True

        return False
    except Exception:
        traceback.print_exc()
        return True


def _heal_timer():
    if not _REGISTERED:
        return None
    try:
        if _hooks_need_repair():
            _log("repairing Blender UI hooks")
            _install_hooks()
    except Exception:
        traceback.print_exc()
    return _HEAL_INTERVAL


def register():
    global _REGISTERED

    try:
        _install_hooks()
    except Exception:
        traceback.print_exc()

    _REGISTERED = True
    if not bpy.app.timers.is_registered(_heal_timer):
        bpy.app.timers.register(_heal_timer, first_interval=_HEAL_INTERVAL, persistent=True)


def unregister():
    global _REGISTERED

    _REGISTERED = False
    if bpy.app.timers.is_registered(_heal_timer):
        try:
            bpy.app.timers.unregister(_heal_timer)
        except Exception:
            pass

    try:
        from bl_ui.space_userpref import USERPREF_PT_addons
        import bl_pkg.bl_extension_ui as ext_ui

        draw_funcs = getattr(getattr(USERPREF_PT_addons, "draw", None), "_draw_funcs", None)
        if draw_funcs is not None:
            for func in list(draw_funcs):
                if _is_our_func(func, "filtered_addons_panel_draw"):
                    draw_funcs.remove(func)
            if _orig_addons_panel_draw is not None and _orig_addons_panel_draw not in draw_funcs:
                draw_funcs.append(_orig_addons_panel_draw)

        if _orig_addons_panel_draw_items is not None:
            ext_ui.addons_panel_draw_items = _orig_addons_panel_draw_items

        tags_panel = getattr(ext_ui, "USERPREF_PT_addons_tags", None)
        if tags_panel is not None:
            tag_funcs = getattr(getattr(tags_panel, "draw", None), "_draw_funcs", None)
            if tag_funcs is not None:
                for func in list(tag_funcs):
                    if _is_our_func(func, "addons_tags_draw"):
                        tag_funcs.remove(func)
    except Exception:
        traceback.print_exc()

    if hasattr(bpy.types.WindowManager, "addon_repo_filter"):
        try:
            del bpy.types.WindowManager.addon_repo_filter
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    register()
