# Linux pywebview: match system WebKit2GTK (4.1 + Soup 3.0, or 4.0 + Soup 2.4).
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
    gi.require_version("Soup", "3.0")
except ValueError:
    gi.require_version("WebKit2", "4.0")
    gi.require_version("Soup", "2.4")
