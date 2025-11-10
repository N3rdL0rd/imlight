import glfw
import OpenGL.GL as gl
from slimgui import imgui
from slimgui.integrations.glfw import GlfwRenderer
import moderngl

from .app import App


def _key_callback(_window, key, _scan, action, _mods):
    pass


def main():
    glfw.init()

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.VISIBLE, True)

    glfw_window = glfw.create_window(
        width=2130, height=1200, title="imlight", monitor=None, share=None
    )
    glfw.make_context_current(glfw_window)

    ctx = moderngl.create_context()
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags.NAV_ENABLE_KEYBOARD
    renderer = GlfwRenderer(glfw_window, prev_key_callback=_key_callback)

    app = App(glfw_window, renderer, ctx)

    while not (glfw.window_should_close(glfw_window)):
        try:
            glfw.poll_events()

            gl.glClear(int(gl.GL_COLOR_BUFFER_BIT) | int(gl.GL_DEPTH_BUFFER_BIT))
            renderer.new_frame()
            imgui.new_frame()

            app.draw()

            imgui.render()
            renderer.render(imgui.get_draw_data())

            glfw.swap_buffers(glfw_window)
        except KeyboardInterrupt:
            break

    renderer.shutdown()
    imgui.destroy_context(None)


if __name__ == "__main__":
    main()
