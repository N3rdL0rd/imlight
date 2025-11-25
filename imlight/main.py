import os
import sys
if os.getenv("XDG_SESSION_TYPE") == "wayland" and not os.getenv("PYOPENGL_PLATFORM"):
    os.environ["PYOPENGL_PLATFORM"] = "x11"

import glfw
import OpenGL.GL as gl
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
import moderngl

from .app import App

def main():
    if not glfw.init():
        print("Could not initialize OpenGL context")
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.VISIBLE, True)

    glfw_window = glfw.create_window(
        width=1920, height=1080, title="imlight", monitor=None, share=None
    )
    
    if not glfw_window:
        glfw.terminate()
        print("Could not initialize Window")
        sys.exit(1)

    glfw.make_context_current(glfw_window)
    glfw.swap_interval(1)

    ctx = moderngl.create_context()
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags_.nav_enable_keyboard
    io.config_flags |= imgui.ConfigFlags_.docking_enable
    io.config_flags |= imgui.ConfigFlags_.viewports_enable
    
    renderer = GlfwRenderer(glfw_window)

    app = App(glfw_window, renderer, ctx)

    while not glfw.window_should_close(glfw_window):
        try:
            glfw.poll_events()
            renderer.process_inputs()

            gl.glClearColor(0.1, 0.1, 0.1, 1)
            gl.glClear(int(gl.GL_COLOR_BUFFER_BIT) | int(gl.GL_DEPTH_BUFFER_BIT))
            
            imgui.new_frame()

            app.draw()

            imgui.render()
            renderer.render(imgui.get_draw_data())

            if io.config_flags & imgui.ConfigFlags_.viewports_enable:
                backup_current_context = glfw.get_current_context()
                imgui.update_platform_windows()
                imgui.render_platform_windows_default()
                glfw.make_context_current(backup_current_context)

            glfw.swap_buffers(glfw_window)
        except KeyboardInterrupt:
            break

    renderer.shutdown()
    glfw.terminate()

if __name__ == "__main__":
    main()