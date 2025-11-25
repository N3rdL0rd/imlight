from __future__ import annotations
import moderngl
import numpy as np
from stl import mesh
from imgui_bundle import imgui
from pyrr import Matrix44, Vector3
from typing import TYPE_CHECKING, Optional, cast
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
    def __init__(self, app: "App"):
        super().__init__("Viz")
        self.app = app
        self.is_open = True
        self.ctx: Optional[moderngl.Context] = None
        self.prog = None
        self.vao = None
        self.fbo = None
        self._fbo_size = (0, 0)
        self.mvp_uniform = None

        self.camera_pos = Vector3([150.0, -150.0, 100.0])
        self.camera_up = Vector3([0.0, 0.0, 1.0])
        target = Vector3([0.0, 0.0, 50.0])
        direction = (target - self.camera_pos).normalized
        self.camera_yaw = np.degrees(np.arctan2(direction.y, direction.x))
        self.camera_pitch = np.degrees(np.arcsin(direction.z))
        self.camera_front = direction

    def init_gl(self, ctx: moderngl.Context):
        """Initialize ModernGL resources. Called after context is ready."""
        self.ctx = ctx
        self.prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        self.mvp_uniform = cast(moderngl.Uniform, self.prog["Mvp"])
        self.vao = self._load_model_from_stl("teapot.stl")

    def _load_model_from_stl(self, filename: str):
        if self.ctx is None: return None
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
            if self.prog:
                return self.ctx.vertex_array(self.prog, [])
            return None

    def _resize_fbo(self, width: float, height: float):
        """Recreates the framebuffer object if the rendering size changes."""
        if self.ctx is None: return

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
        # Usually docking layout handles position/size, but this sets defaults for free-floating
        imgui.set_next_window_pos(imgui.ImVec2(580, 30), imgui.Cond_.first_use_ever)
        imgui.set_next_window_size(imgui.ImVec2(780, 480), imgui.Cond_.first_use_ever)

    def draw_content(self):
        """Renders the 3D scene to a texture, then draws that texture in the window."""
        if self.ctx is None:
            imgui.text("Initializing GL...")
            return

        content_size = imgui.get_content_region_avail()
        self._resize_fbo(content_size.x, content_size.y)

        if not self.fbo or not self.vao:
            imgui.text("Could not load 3D model or FBO.")
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

        if self.mvp_uniform:
            self.mvp_uniform.write(mvp.astype("f4"))
        self.vao.render()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.screen.use() # Switch back to default screen

        texture_id = self.fbo.color_attachments[0].glo

        # Interaction area
        imgui.push_id("viz_content_interaction")
        imgui.invisible_button("##viz_content", imgui.ImVec2(self._fbo_size[0], self._fbo_size[1]))

        # Draw the texture
        draw_list = imgui.get_window_draw_list()
        min_pos = imgui.get_item_rect_min()
        max_pos = imgui.get_item_rect_max()
        
        ref = imgui.ImTextureRef(texture_id)
        draw_list.add_image(ref, min_pos, max_pos, (0, 1), (1, 0))

        io = imgui.get_io()
        
        if imgui.is_item_hovered():
            if io.mouse_wheel != 0:
                self.camera_pos += self.camera_front * io.mouse_wheel * 5.0

            if imgui.is_mouse_dragging(imgui.MouseButton_.left):
                delta = io.mouse_delta
                sensitivity = 0.1
                self.camera_yaw -= delta.x * sensitivity
                self.camera_pitch -= delta.y * sensitivity

                if self.camera_pitch > 89.0:
                    self.camera_pitch = 89.0
                if self.camera_pitch < -89.0:
                    self.camera_pitch = -89.0
        imgui.pop_id()

        if imgui.is_mouse_dragging(imgui.MouseButton_.right):
            delta = io.mouse_delta
            pan_speed = 0.1

            right_vector = Vector3.cross(self.camera_front, self.camera_up).normalized

            self.camera_pos -= right_vector * delta.x * pan_speed
            self.camera_pos += self.camera_up * delta.y * pan_speed

    def __del__(self):
        """Clean up ModernGL resources."""
        if self.fbo:
            self.fbo.release()
        if self.vao:
            self.vao.release()
        if self.prog:
            self.prog.release()