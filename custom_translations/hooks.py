app_name = "custom_translations"
app_title = "Custom Translations"
app_publisher = "Open Source"
app_description = "Independent Chinese translations for Frappe/ERPNext with auto-fill mechanism. Survives framework upgrades."
app_email = ""
app_license = "MIT"

# Independent translations: Frappe will auto-load translations/zh.csv from this app
# and merge with translations from other apps. Later apps override earlier ones.
# This app loads AFTER frappe/erpnext, so our translations take priority.
# This app does NOT modify any official frappe/erpnext files - all translations
# are injected via hooks and the app's own CSV file.

# Inject missing translation detection + setup hints on boot
extend_bootinfo = [
    "custom_translations.utils.detect_missing_translations_bootinfo",
]

# Listen to Translation doctype changes to refresh cache
doc_events = {
    "Translation": {
        "on_update": "custom_translations.utils.on_translation_update",
    }
}

# Show setup instructions after installation
after_install = "custom_translations.setup.after_install"

# Custom bench commands
bench_commands = [
    "custom_translations.commands",
]

