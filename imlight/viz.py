# viz.py

from __future__ import annotations
import glfw
import moderngl
import numpy as np
from stl import mesh
from slimgui import imgui
from pyrr import Matrix44
from typing import TYPE_CHECKING
from .window import Window

if TYPE_CHECKING:
    from .app import App

# --- 1. The Simplest Shaders ---
# Vertex shader just transforms the vertex position.
vert = """
    #version 330
    uniform mat4 Mvp;
    in vec3 in_vert;
    void main() {
        gl_Position = Mvp * vec4(in_vert, 1.0);
    }
"""

# Fragment shader outputs a single, hardcoded color.
frag = """
    #version 330
    out vec4 f_color;
    void main() {
        f_color = vec4(0.8, 0.2, 0.2, 1.0);
    }
"""

class VizWindow(Window):
    def __init__(self, app: "App", ctx: moderngl.Context):
        super().__init__("Viz")
        self.app = app
        self.ctx = ctx
        self.is_open = True

        # --- 2. Setup a Simple Program and Uniform ---
        self.prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        self.mvp_uniform = self.prog['Mvp']

        # --- 3. Load the Model ---
        self.vao = self._load_model_from_stl('teapot.stl')

        # Framebuffer for off-screen rendering
        self.fbo = None
        self._fbo_size = (0, 0)

    def _load_model_from_stl(self, filename: str):
        """
        The simplest way to load an STL.
        Just grabs the vertices and sends them to the GPU.
        """
        try:
            mesh_data = mesh.Mesh.from_file(filename)

            # The STL's 'vectors' are triangles. We reshape them into a flat
            # list of vertices. This is all the data we need.
            vertices = mesh_data.vectors.reshape(-1, 3).astype('f4')

            # Create a Vertex Buffer Object (VBO) and send the vertex data to it.
            vbo = self.ctx.buffer(vertices.tobytes())

            # Create a Vertex Array Object (VAO) to describe the VBO's layout.
            # '3f' means each vertex is made of 3 floating-point numbers.
            # 'in_vert' is the name of the input in our vertex shader.
            return self.ctx.vertex_array(self.prog, [(vbo, '3f', 'in_vert')])

        except FileNotFoundError:
            print(f"Error: Model file '{filename}' not found.")
            return self.ctx.vertex_array(self.prog, []) # Return an empty VAO
        except Exception as e:
            print(f"Error loading STL model: {e}")
            return self.ctx.vertex_array(self.prog, [])

    def _resize_fbo(self, width: float, height: float):
        """Recreates the framebuffer object if the rendering size changes."""
        width, height = int(width), int(height)
        if width <= 0 or height <= 0 or (self.fbo and self._fbo_size == (width, height)):
            return

        if self.fbo: self.fbo.release()

        self._fbo_size = (width, height)
        color_attachment = self.ctx.texture(self._fbo_size, 4)
        depth_attachment = self.ctx.depth_texture(self._fbo_size)
        self.fbo = self.ctx.framebuffer(
            color_attachments=[color_attachment], depth_attachment=depth_attachment
        )

    def pre_draw(self):
        imgui.set_next_window_pos((580, 30), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((780, 480), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        """Renders the 3D scene to a texture, then draws that texture in the window."""
        content_size = imgui.get_content_region_avail()
        self._resize_fbo(content_size[0], content_size[1])

        if not self.fbo or not self.vao or self.vao.vertices == 0:
            imgui.text("Could not load 3D model.")
            return

        # --- 4. Render the Scene ---
        # Activate our off-screen framebuffer
        self.fbo.use()
        self.ctx.clear(0.12, 0.12, 0.12)
        self.ctx.enable(moderngl.DEPTH_TEST)

        # --- Create Fixed Camera Matrices ---
        aspect_ratio = 1.0
        if self._fbo_size[1] > 0:
            aspect_ratio = self._fbo_size[0] / self._fbo_size[1]

        # A fixed projection matrix
        proj = Matrix44.perspective_projection(45.0, aspect_ratio, 0.1, 1000.0)
        # A fixed camera looking at the origin from a distance
        lookat = Matrix44.look_at(
            eye=(150, -150, 150), target=(0, 0, 50), up=(0, 0, 1)
        )
        # A simple rotation to make it look 3D
        model = Matrix44.from_z_rotation(glfw.get_time() * 0.5)

        # Combine them into a single Model-View-Projection matrix
        mvp = proj * lookat * model
        
        # --- Send data and render ---
        self.mvp_uniform.write(mvp.astype('f4'))
        self.vao.render()

        # --- 5. Display in ImGui ---
        # Restore OpenGL state for ImGui
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.screen.use()

        # Get the OpenGL texture ID from our framebuffer
        texture_id = self.fbo.color_attachments[0].glo
        
        # Draw the texture as an image in the ImGui window
        imgui.image(
            texture_id,
            self._fbo_size,
            uv0=(0, 1),
            uv1=(1, 0),
        )

    def __del__(self):
        """Clean up ModernGL resources when the window is closed."""
        if self.fbo: self.fbo.release()
        if self.vao: self.vao.release()
        self.prog.release()