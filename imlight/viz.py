# viz.py

from __future__ import annotations

import glfw
import moderngl
import numpy as np
from stl import mesh
import math
from slimgui import imgui
import pyrr  # <-- Use the full pyrr library for explicit function calls
from typing import TYPE_CHECKING

from .window import Window

if TYPE_CHECKING:
    from .app import App

# Shaders remain the same
vert = """
    #version 330
    uniform mat4 M; uniform mat4 V; uniform mat4 P;
    in vec3 in_vert; in vec3 in_normal;
    out vec3 v_normal_view; out vec3 v_pos_view;

    void main() {
        vec4 pos_world = M * vec4(in_vert, 1.0);
        vec4 pos_view = V * pos_world;
        v_pos_view = pos_view.xyz;
        v_normal_view = mat3(transpose(inverse(V * M))) * in_normal;
        gl_Position = P * pos_view;
    }
"""

frag = """
    #version 330
    uniform vec3 LightDirView; uniform vec4 ObjectColor;
    in vec3 v_normal_view; in vec3 v_pos_view;
    out vec4 f_color;

    void main() {
        float ambient_strength = 0.3; float diffuse_strength = 0.7;
        float specular_strength = 0.5; float shininess = 32.0;

        vec3 N = normalize(v_normal_view); vec3 L = normalize(LightDirView);
        vec3 E = normalize(-v_pos_view); vec3 H = normalize(L + E);

        vec3 ambient = ambient_strength * ObjectColor.rgb;
        float diff = max(dot(N, L), 0.0);
        vec3 diffuse = diffuse_strength * diff * ObjectColor.rgb;
        float spec = pow(max(dot(N, H), 0.0), shininess);
        vec3 specular = specular_strength * spec * vec3(1.0, 1.0, 1.0);

        vec3 final_color = ambient + diffuse + specular;
        f_color = vec4(final_color, ObjectColor.a);
    }
"""

class VizWindow(Window):
    def __init__(self, app: "App", ctx: moderngl.Context):
        super().__init__("Viz")
        self.app = app
        self.ctx = ctx
        self.is_open = True

        self.camera_distance = 2.5
        self.camera_phi = math.radians(20)
        self.camera_theta = math.radians(70)
        self.camera_target = pyrr.Vector3([0.0, 0.0, 0.0])

        self.prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        self.uniform_M = self.prog['M']
        self.uniform_V = self.prog['V']
        self.uniform_P = self.prog['P']
        self.uniform_light_dir = self.prog['LightDirView']
        self.uniform_object_color = self.prog['ObjectColor']

        self.vao, self.model_matrix = self._load_model_from_stl('teapot.stl')

        self.fbo = None
        self._fbo_size = (0, 0)
    
    def _load_model_from_stl(self, filename: str):
        try:
            mesh_data = mesh.Mesh.from_file(filename)
            _, cog, _ = mesh_data.get_mass_properties()
            self.camera_target = pyrr.Vector3(cog)
            
            scale = (mesh_data.max_ - mesh_data.min_).max()
            
            # Use explicit pyrr functions for matrix creation
            scale_matrix = pyrr.matrix44.create_from_scale([1.0 / scale] * 3)
            translate_matrix = pyrr.matrix44.create_from_translation(-self.camera_target)
            model_matrix = pyrr.matrix44.multiply(scale_matrix, translate_matrix)

            normals = mesh_data.normals
            vertices = mesh_data.vectors
            flat_normals = np.repeat(normals, 3, axis=0)
            flat_vertices = vertices.reshape(-1, 3)
            interleaved_data = np.hstack([flat_normals, flat_vertices]).astype('f4')

            vbo = self.ctx.buffer(interleaved_data.tobytes())
            vao = self.ctx.vertex_array(
                self.prog,
                [(vbo, '3f 3f', 'in_normal', 'in_vert')]
            )
            return vao, model_matrix

        except FileNotFoundError:
            print(f"Error: Model file '{filename}' not found.")
            return self.ctx.vertex_array(self.prog, []), pyrr.matrix44.create_identity()
        except Exception as e:
            print(f"Error loading model: {e}")
            return self.ctx.vertex_array(self.prog, []), pyrr.matrix44.create_identity()

    def _resize_fbo(self, width: float, height: float):
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

    def _handle_camera_controls(self):
        io = imgui.get_io()
        if not imgui.is_item_hovered():
            return

        scroll = io.mouse_wheel
        if scroll != 0:
            self.camera_distance = max(0.5, self.camera_distance - scroll * 0.2)

        if imgui.is_mouse_dragging(imgui.MouseButton.LEFT):
            delta = io.mouse_delta
            self.camera_phi -= delta[0] * 0.01
            self.camera_theta = np.clip(self.camera_theta - delta[1] * 0.01, 0.1, math.pi - 0.1)

    def pre_draw(self):
        imgui.set_next_window_pos((580, 30), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((780, 480), imgui.Cond.FIRST_USE_EVER)
        if imgui.is_item_active():
             self.window_flags |= imgui.WindowFlags.NO_MOVE
        else:
             self.window_flags &= ~imgui.WindowFlags.NO_MOVE

    def draw_content(self):
        content_size = imgui.get_content_region_avail()
        self._resize_fbo(content_size[0], content_size[1])

        if not self.fbo or not self.vao or self.vao.vertices == 0:
            imgui.text("Could not load 3D model.")
            return

        self.fbo.use()
        self.ctx.clear(0.12, 0.12, 0.12)
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)

        aspect_ratio = self._fbo_size[0] / self._fbo_size[1] if self._fbo_size[1] > 0 else 1.0

        eye_x = self.camera_distance * math.sin(self.camera_theta) * math.cos(self.camera_phi)
        eye_y = self.camera_distance * math.cos(self.camera_theta)
        eye_z = self.camera_distance * math.sin(self.camera_theta) * math.sin(self.camera_phi)
        eye = pyrr.Vector3([eye_x, eye_y, eye_z]) + self.camera_target

        proj_matrix = pyrr.matrix44.create_perspective_projection(45.0, aspect_ratio, 0.1, 100.0)
        view_matrix = pyrr.matrix44.create_look_at(eye, self.camera_target, pyrr.Vector3([0.0, 1.0, 0.0]))
        
        self.uniform_P.write(proj_matrix.astype('f4'))
        self.uniform_V.write(view_matrix.astype('f4'))
        self.uniform_M.write(self.model_matrix.astype('f4'))
        self.uniform_object_color.value = (0.8, 0.2, 0.2, 1.0)

        # --------------------- THE DEFINITIVE FIX IS HERE ---------------------
        light_dir_world = pyrr.Vector4([2.0, 3.0, 4.0, 0.0])
        
        # Use the explicit function to transform the vector by the matrix
        light_dir_view_vec4 = pyrr.matrix44.apply_to_vector(view_matrix, light_dir_world)
        
        # Normalize the resulting vector using the explicit function
        light_dir_view_normalized = pyrr.vector.normalize(light_dir_view_vec4)
        # ----------------------------------------------------------------------
        
        self.uniform_light_dir.value = tuple(light_dir_view_normalized)

        self.vao.render()

        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.screen.use()

        texture_id = self.fbo.color_attachments[0].glo
        imgui.image(texture_id, self._fbo_size, uv0=(0, 1), uv1=(1, 0))
        self._handle_camera_controls()

    def __del__(self):
        if self.fbo: self.fbo.release()
        if self.vao: self.vao.release()
        self.prog.release()