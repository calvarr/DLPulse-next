# Force WebKit2GTK 4.0 + libsoup 2.4 from the AppImage bundle (Ubuntu 22.04 CI).
# pywebview tries 4.1 first; on Arch/Manjaro that loads incompatible system typelibs.
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.0")
gi.require_version("Soup", "2.4")
