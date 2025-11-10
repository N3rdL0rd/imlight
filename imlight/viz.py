# viz.py

from __future__ import annotations
import glfw
import moderngl
import numpy as np
from stl import mesh
from slimgui import imgui
from pyrr import Matrix44, Vector3
from typing import TYPE_CHECKING
from .window import Window

if TYPE_CHECKING:
    from .app import App

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

        self.prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        mvp = self.prog["Mvp"]
        assert isinstance(mvp, moderngl.Uniform)
        self.mvp_uniform = mvp

        self.vao = self._load_model_from_stl("teapot.stl")

        self.fbo = None
        self._fbo_size = (0, 0)

        self.camera_pos = Vector3([150.0, -150.0, 100.0])
        self.camera_up = Vector3([0.0, 0.0, 1.0])
        target = Vector3([0.0, 0.0, 50.0])
        direction = (target - self.camera_pos).normalized
        self.camera_yaw = np.degrees(np.arctan2(direction.y, direction.x))
        self.camera_pitch = np.degrees(np.arcsin(direction.z))
        self.camera_front = direction

    def _load_model_from_stl(self, filename: str):
        """
        The simplest way to load an STL.
        Just grabs the vertices and sends them to the GPU.
        """
        try:
            mesh_data = mesh.Mesh.from_file(filename)
            vertices = mesh_data.vectors.reshape(-1, 3).astype("f4")
            vbo = self.ctx.buffer(vertices.tobytes())
            return self.ctx.vertex_array(self.prog, [(vbo, "3f", "in_vert")])

        except FileNotFoundError:
            print(f"Error: Model file '{filename}' not found.")
            return self.ctx.vertex_array(self.prog, [])
        except Exception as e:
            print(f"Error loading STL model: {e}")
            return self.ctx.vertex_array(self.prog, [])

    def _resize_fbo(self, width: float, height: float):
        """Recreates the framebuffer object if the rendering size changes."""
        width, height = int(width), int(height)
        if (
            width <= 0
            or height <= 0
            or (self.fbo and self._fbo_size == (width, height))
        ):
            return

        if self.fbo:
            self.fbo.release()

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

        self.fbo.use()
        self.ctx.clear(0.12, 0.12, 0.12)
        self.ctx.enable(moderngl.DEPTH_TEST)

        aspect_ratio = 1.0
        if self._fbo_size[1] > 0:
            aspect_ratio = self._fbo_size[0] / self._fbo_size[1]

        yaw_rad = np.radians(self.camera_yaw)
        pitch_rad = np.radians(self.camera_pitch)

        front = Vector3()
        front.x = np.cos(yaw_rad) * np.cos(pitch_rad)
        front.y = np.sin(yaw_rad) * np.cos(pitch_rad)
        front.z = np.sin(pitch_rad)
        self.camera_front = front.normalized

        proj = Matrix44.perspective_projection(45.0, aspect_ratio, 0.1, 1000.0)
        lookat = Matrix44.look_at(
            eye=self.camera_pos,
            target=self.camera_pos + self.camera_front,
            up=self.camera_up,
        )
        model = Matrix44.identity()
        mvp = proj * lookat * model

        self.mvp_uniform.write(mvp.astype("f4"))
        self.vao.render()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.screen.use()

        texture_id = self.fbo.color_attachments[0].glo

        imgui.push_id("viz_content_interaction")
        imgui.invisible_button("##viz_content", self._fbo_size)

        draw_list = imgui.get_window_draw_list()
        min_pos = imgui.get_item_rect_min()
        max_pos = imgui.get_item_rect_max()
        draw_list.add_image(texture_id, min_pos, max_pos, uv_min=(0, 1), uv_max=(1, 0))

        io = imgui.get_io()
        
        if imgui.is_item_hovered():
            if io.mouse_wheel != 0:
                self.camera_pos += self.camera_front * io.mouse_wheel * 5.0

            if imgui.is_mouse_dragging(imgui.MouseButton.LEFT):
                delta = io.mouse_delta
                sensitivity = 0.1
                self.camera_yaw -= delta[0] * sensitivity
                self.camera_pitch -= delta[1] * sensitivity

                if self.camera_pitch > 89.0:
                    self.camera_pitch = 89.0
                if self.camera_pitch < -89.0:
                    self.camera_pitch = -89.0
        imgui.pop_id()

        if imgui.is_mouse_dragging(imgui.MouseButton.RIGHT):
            delta = io.mouse_delta
            pan_speed = 0.1

            right_vector = Vector3.cross(self.camera_front, self.camera_up).normalized

            self.camera_pos -= right_vector * delta[0] * pan_speed
            self.camera_pos += self.camera_up * delta[1] * pan_speed

    def __del__(self):
        """Clean up ModernGL resources when the window is closed."""
        if self.fbo:
            self.fbo.release()
        if self.vao:
            self.vao.release()
        self.prog.release()
