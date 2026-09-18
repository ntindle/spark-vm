#!/bin/bash
# Launch the Blender GUI on the CUA desktop (:98) with the demo file.
# Blender 5.x prefers Wayland via $XDG_RUNTIME_DIR/wayland-0 even when
# WAYLAND_DISPLAY is empty (this box runs a GNOME/Wayland session) --
# unset both so Blender uses pure X11 on :98.
unset XDG_RUNTIME_DIR WAYLAND_DISPLAY
export GDK_BACKEND=x11 XDG_SESSION_TYPE=x11
exec $HOME/bin/blender $HOME/cua/demo.blend
