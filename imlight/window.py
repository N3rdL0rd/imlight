from typing import Tuple, cast, Optional
import numpy as np
from OpenGL import GL
from imgui_bundle import imgui
from abc import ABC, abstractmethod
from PIL import Image


def create_texture_from_numpy(pixels: np.ndarray) -> int:
    """Creates an OpenGL texture from a NumPy array."""
    height, width, channels = pixels.shape

    texture_id = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)

    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

    if channels == 3:
        fmt = GL.GL_RGB
    elif channels == 4:
        fmt = GL.GL_RGBA
    else:
        raise ValueError("Image must be RGB or RGBA")

    GL.glTexImage2D(
        GL.GL_TEXTURE_2D, 0, fmt, width, height, 0, fmt, GL.GL_UNSIGNED_BYTE, pixels
    )

    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
    return texture_id


def update_texture_from_numpy(texture_id: int, pixels: np.ndarray) -> None:
    """Updates an existing OpenGL texture with data from a NumPy array."""
    height, width, channels = pixels.shape

    if channels == 3:
        fmt = GL.GL_RGB
    elif channels == 4:
        fmt = GL.GL_RGBA
    else:
        raise ValueError("Image must be RGB or RGBA")

    GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
    GL.glTexSubImage2D(
        GL.GL_TEXTURE_2D, 0, 0, 0, width, height, fmt, GL.GL_UNSIGNED_BYTE, pixels
    )
    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)


class Window(ABC):
    """
    The updated base class.
    For HelloImGui, we usually use 'callBeginEnd=False' in DockableWindow options
    so we can control the window flags and constraints here.
    """

    def __init__(self, title: str):
        self.title = title
        self.is_open: bool = True
        self.window_flags: int = imgui.WindowFlags_.none

    def draw(self):
        """
        The template method for drawing a window.
        """
        if not self.is_open:
            return

        self.pre_draw()

        # Note: HelloImGui handles docking, but if we manage Begin/End ourselves
        # (callBeginEnd=False in DockableWindow), we must ensure the name matches.
        
        io = imgui.get_io()
        flags = self.window_flags
        if io.key_ctrl:
            flags |= imgui.WindowFlags_.no_move

        # imgui_bundle: begin returns (should_draw, p_open_state)
        opened, isopen = imgui.begin(self.title, self.is_open, flags)
        if isopen is not None:
            self.is_open = isopen
            

        if not self.is_open:
            self.on_close()

        if opened:
            self.draw_content()

        imgui.end()
        self.post_draw()

    def pre_draw(self):
        """Optional hook for subclasses, called before imgui.begin()."""
        pass

    def post_draw(self):
        """Optional hook for subclasses, called after imgui.end()."""
        pass

    @abstractmethod
    def draw_content(self):
        """Subclasses MUST implement this to draw their unique content."""
        pass

    def on_close(self):
        """Optional hook called when the window is closed by the user."""
        pass


class ImguiAboutWindow(Window):
    def __init__(self):
        super().__init__("About imgui")
        self.is_open = False

    def draw(self):
        if self.is_open:
            res = imgui.show_about_window(self.is_open)
            if res is not None:
                self.is_open = res

    def draw_content(self):
        pass


class CanvasWindow(Window, ABC):
    """
    An abstract base class for an ImGui window that displays a pixel buffer.
    """

    def __init__(self, title: str, width: int, height: int):
        super().__init__(title)
        self.width = width
        self.height = height
        self.pixels = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.texture_id: Optional[int] = None

    def _ensure_texture(self):
        if self.texture_id is None:
            self.texture_id = create_texture_from_numpy(self.pixels)

    def draw(self):
        self._ensure_texture()
        super().draw()

    def draw_content(self):
        self.draw_controls()
        self.update_pixels(self.pixels)

        if self.texture_id is not None:
            update_texture_from_numpy(self.texture_id, self.pixels)
            ref = imgui.ImTextureRef(self.texture_id)
            imgui.image(ref, imgui.ImVec2(self.width, self.height))

        self.handle_interaction()

    @abstractmethod
    def update_pixels(self, pixels: np.ndarray):
        pass

    def draw_controls(self):
        pass

    def handle_interaction(self):
        pass

    def __del__(self):
        if self.texture_id is not None:
            try:
                GL.glDeleteTextures([self.texture_id])
            except:
                pass
            self.texture_id = None


class CanvasFullWindow(Window, ABC):
    def __init__(self, title: str, width: int, height: int, closable: bool = True):
        super().__init__(title)
        self.width = width
        self.height = height
        self.closable = closable
        self.is_open = True
        self.pixels = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.texture_id: Optional[int] = None

    def _ensure_texture(self):
        if self.texture_id is None:
            self.texture_id = create_texture_from_numpy(self.pixels)

    def draw(self):
        if not self.is_open:
            return
        
        self._ensure_texture()

        imgui.push_style_var(imgui.StyleVar_.window_padding, (0, 0))
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0)
        imgui.set_next_window_content_size(imgui.ImVec2(self.width, self.height))

        flags = imgui.WindowFlags_.no_scrollbar | imgui.WindowFlags_.no_scroll_with_mouse

        io = imgui.get_io()
        if io.key_ctrl:
            flags |= imgui.WindowFlags_.no_move

        opened, isopen = imgui.begin(self.title, self.is_open if self.closable else None, flags)
        if isopen is not None:
            self.is_open = isopen

        if opened:
            self.update_pixels(self.pixels)
            if self.texture_id is not None:
                update_texture_from_numpy(self.texture_id, self.pixels)
                ref = imgui.ImTextureRef(self.texture_id)
                imgui.image(ref, imgui.ImVec2(self.width, self.height))
            self.handle_interaction()

        imgui.end()
        imgui.pop_style_var(2)

    @abstractmethod
    def update_pixels(self, pixels: np.ndarray):
        pass

    def handle_interaction(self):
        pass

    def __del__(self):
        if self.texture_id is not None:
            try:
                GL.glDeleteTextures([self.texture_id])
            except:
                pass
            self.texture_id = None


class AspectLockedWindow(Window, ABC):
    def __init__(self, title: str, aspect_ratio: float):
        super().__init__(title)
        if aspect_ratio <= 0:
            raise ValueError("Aspect ratio must be positive.")
        self.aspect_ratio = aspect_ratio

    def pre_draw(self):
        super().pre_draw()
        # Callback for size constraints
        def aspect_cb(data: imgui.SizeCallbackData):
            data.desired_size = imgui.ImVec2(data.desired_size.x, data.desired_size.x / self.aspect_ratio)

        imgui.set_next_window_size_constraints(
            imgui.ImVec2(100, 100 / self.aspect_ratio),
            imgui.ImVec2(5000, 2000 / self.aspect_ratio),
            aspect_cb,
        )


class TexturedWindow(AspectLockedWindow, ABC):
    def __init__(self, title: str, aspect_ratio: float, image_path: str):
        super().__init__(title, aspect_ratio)
        self.image_path = image_path
        self.texture_id: Optional[int] = None
        self.pixels: Optional[np.ndarray] = None
        self.app = None # Will be set by App class

    def _ensure_texture(self):
        if self.texture_id is None:
            try:
                with Image.open(self.image_path) as img:
                    img = img.convert("RGBA")
                    self.pixels = np.array(img, dtype=np.uint8)
                    self.texture_id = create_texture_from_numpy(self.pixels)
            except FileNotFoundError:
                print(f"Error: Background image not found at '{self.image_path}'")
            except Exception as e:
                print(f"Error loading image: {e}")

    def draw(self):
        if not self.is_open:
            return
        
        self._ensure_texture()
        self.pre_draw()

        draw_background_image = True
        try:
            # Check app state if available
            if self.app and self.app.stage_config.map_mode != self.app.stage_config.MapMode.IMAGE: # type: ignore
                draw_background_image = False
        except AttributeError:
            pass

        io = imgui.get_io()
        flags = (
            self.window_flags
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_background
        )
        if io.key_ctrl:
            flags |= imgui.WindowFlags_.no_move

        opened, isopen = imgui.begin(self.title, self.is_open, flags)
        if isopen is not None:
            self.is_open = isopen

        if opened:
            if draw_background_image and self.texture_id is not None:
                draw_list = imgui.get_background_draw_list()
                pos = imgui.get_window_pos()
                size = imgui.get_window_size()
                ref = imgui.ImTextureRef(self.texture_id)
                draw_list.add_image(
                    ref, pos, imgui.ImVec2(pos.x + size.x, pos.y + size.y)
                )

            self.draw_content()

        imgui.end()
        self.post_draw()

    def __del__(self):
        if self.texture_id is not None:
            try:
                GL.glDeleteTextures([self.texture_id])
            except:
                pass
            self.texture_id = None