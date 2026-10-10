app_name = "custom_translations"
app_title = "Custom Translations"
app_publisher = "Open Source"
app_description = (
    "Independent Simplified-Chinese translations for the Frappe ecosystem "
    "(frappe, erpnext, hrms, payments, wiki, helpdesk, webshop, telephony). "
    "Ships a curated CSV override layer, a coverage scanner that understands "
    "both the `translations/*.csv` and `locale/*.po` layouts, and an optional "
    "AI auto-fill pipeline."
)
app_email = ""
app_license = "MIT"

# --------------------------------------------------------------------------- #
# Translation loading
# --------------------------------------------------------------------------- #
# Frappe merges `translations/<lang>.csv` from every installed app
# (`frappe.translate.get_translations_from_apps`). Apps installed *after* this
# one win over it, so install this app last if you want it to be authoritative.
# This app never modifies official frappe/erpnext files.

# --------------------------------------------------------------------------- #
# Hooks
# --------------------------------------------------------------------------- #
# NOTE: bench commands are NOT registered through a hook. Frappe/bench imports
# `<app>.commands` and reads its `commands` list
# (`frappe/utils/bench_helper.py: get_app_commands`), which is what
# custom_translations/commands.py provides. A `bench_commands` hook does not
# exist and would be silently ignored.

# Log newly detected untranslated strings to the Missing Translation Log.
# The scan is cached (default 6h, see `scan_interval_seconds`) so a desk boot
# never pays for a full PO/POT scan.
extend_bootinfo = [
    "custom_translations.utils.detect_missing_translations_bootinfo",
]

# Keep the CSV in sync when a Translation record is edited in the desk.
doc_events = {
    "Translation": {
        "on_update": "custom_translations.utils.on_translation_update",
    }
}

# Safety net for sites that disable the boot scan: a full scan + optional
# auto-translation once a day.
scheduler_events = {
    "daily": [
        "custom_translations.utils.scheduled_translation_scan",
    ],
}

# Show setup instructions after installation
# (`custom_translations.setup`, not the pip-level setup.py).
after_install = "custom_translations.setup.after_install"
