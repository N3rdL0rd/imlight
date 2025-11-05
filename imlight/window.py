from typing import Tuple
import numpy as np
from OpenGL import GL
from slimgui import imgui
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
    The updated base class with pre/post draw hooks and a close hook.
    """

    def __init__(self, title: str):
        self.title = title
        self.is_open: bool = True

    def draw(self):
        """
        The template method for drawing a window. Subclasses should not override this.
        It orchestrates the pre_draw, begin, draw_content, end, and post_draw calls.
        """
        self.pre_draw()

        io = imgui.get_io()
        flags = imgui.WindowFlags.NONE
        if io.key_ctrl:
            flags |= imgui.WindowFlags.NO_MOVE

        was_open = self.is_open
        opened, self.is_open = imgui.begin(self.title, closable=True, flags=flags)

        if was_open and not self.is_open:
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
            io = imgui.get_io()
            if io.key_ctrl:
                pass

            self.is_open = imgui.show_about_window(closable=True)

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

        self.texture_id = create_texture_from_numpy(self.pixels)

    def draw(self):
        """The main rendering method."""
        io = imgui.get_io()
        flags = imgui.WindowFlags.NONE
        if io.key_ctrl:
            flags |= imgui.WindowFlags.NO_MOVE

        imgui.begin(self.title, flags=flags)

        self.draw_controls()
        self.update_pixels(self.pixels)

        assert self.texture_id is not None
        update_texture_from_numpy(self.texture_id, self.pixels)
        imgui.image(self.texture_id, (self.width, self.height))

        self.handle_interaction()
        imgui.end()

    @abstractmethod
    def update_pixels(self, pixels: np.ndarray):
        """
        Subclasses MUST implement this method.
        """
        pass

    def draw_controls(self):
        """
        Subclasses can optionally override this.
        """
        pass

    def handle_interaction(self):
        """
        Subclasses can optionally override this.
        """
        pass

    def __del__(self):
        """Ensures the OpenGL texture is deleted when the object is destroyed."""
        if self.texture_id is not None:
            GL.glDeleteTextures([self.texture_id])
            self.texture_id = None


class CanvasFullWindow(Window, ABC):
    """
    An abstract base class for an ImGui window that tightly encapsulates a
    pixel buffer, with no padding or borders around the image.
    """

    def __init__(self, title: str, width: int, height: int, closable: bool = True):
        super().__init__(title)
        self.width = width
        self.height = height
        self.closable = closable
        self.is_open = True

        self.pixels = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.texture_id = create_texture_from_numpy(self.pixels)

    def draw(self):
        """The main rendering method that ensures a tight fit."""
        if not self.is_open:
            return

        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, (0, 0))
        imgui.push_style_var(imgui.StyleVar.WINDOW_BORDER_SIZE, 0)
        imgui.set_next_window_content_size((self.width, self.height))

        flags = imgui.WindowFlags.NO_SCROLLBAR | imgui.WindowFlags.NO_SCROLL_WITH_MOUSE

        # --- GLOBAL DRAG-DISABLE LOGIC (for this custom draw method) ---
        io = imgui.get_io()
        if io.key_ctrl:
            flags |= imgui.WindowFlags.NO_MOVE

        opened, self.is_open = imgui.begin(
            self.title, closable=self.closable, flags=flags
        )

        if opened:
            self.update_pixels(self.pixels)
            assert self.texture_id is not None
            update_texture_from_numpy(self.texture_id, self.pixels)
            imgui.image(self.texture_id, (self.width, self.height))
            self.handle_interaction()

        imgui.end()
        imgui.pop_style_var(2)

    @abstractmethod
    def update_pixels(self, pixels: np.ndarray):
        """Subclasses MUST implement this to define the canvas content."""
        pass

    def handle_interaction(self):
        """Optional hook for subclasses to handle mouse interaction."""
        pass

    def __del__(self):
        """Ensures the OpenGL texture is deleted."""
        if self.texture_id is not None:
            GL.glDeleteTextures([self.texture_id])
            self.texture_id = None


class AspectLockedWindow(Window, ABC):
    """A window that maintains a constant aspect ratio when resized."""

    def __init__(self, title: str, aspect_ratio: float):
        super().__init__(title)
        if aspect_ratio <= 0:
            raise ValueError("Aspect ratio must be positive.")
        self.aspect_ratio = aspect_ratio

    def get_aspect_ratio_func(self):
        aspect_ratio = self.aspect_ratio

        def cb(
            _pos: Tuple[float, float],
            _current_size: Tuple[float, float],
            desired_size: Tuple[float, float],
            _int_user_data: int,
        ) -> Tuple[float, float]:
            nonlocal aspect_ratio
            new_desired_y = int(desired_size[0] / aspect_ratio)
            return (desired_size[0], new_desired_y)

        return cb

    def pre_draw(self):
        """Set the resize constraints before the window is drawn."""
        super().pre_draw()
        imgui.set_next_window_size_constraints(
            size_min=(100, 100 / self.aspect_ratio),
            size_max=(5000, 2000 / self.aspect_ratio),
            cb=self.get_aspect_ratio_func(),
        )


class TexturedWindow(AspectLockedWindow, ABC):
    """An aspect-locked window with an image drawn over its entire background."""

    def __init__(self, title: str, aspect_ratio: float, image_path: str):
        super().__init__(title, aspect_ratio)
        self.texture_id = None
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGBA")
                pixels = np.array(img, dtype=np.uint8)
                self.texture_id = create_texture_from_numpy(pixels)
        except FileNotFoundError:
            print(f"Error: Background image not found at '{image_path}'")
        except Exception as e:
            print(f"Error loading image: {e}")

    def draw(self):
        """Custom draw method to render the background image."""
        if not self.is_open:
            return

        self.pre_draw()

        io = imgui.get_io()
        flags = imgui.WindowFlags.NO_SCROLLBAR  # No scrollbar for this type of window
        if io.key_ctrl:
            flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_BACKGROUND

        was_open = self.is_open
        opened, self.is_open = imgui.begin(self.title, closable=True, flags=flags)

        if was_open and not self.is_open:
            self.on_close()

        if opened:
            if self.texture_id is not None:
                draw_list = imgui.get_background_draw_list()
                pos = imgui.get_window_pos()
                size = imgui.get_window_size()
                draw_list.add_image(
                    self.texture_id, pos, (pos[0] + size[0], pos[1] + size[1])
                )

            self.draw_content()

        imgui.end()
        self.post_draw()

    def __del__(self):
        """Clean up the OpenGL texture."""
        if self.texture_id is not None:
            GL.glDeleteTextures([self.texture_id])
            self.texture_id = None
