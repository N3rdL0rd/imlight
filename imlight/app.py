from slimgui.integrations.glfw import GlfwRenderer
from typing import Any
from slimgui import imgui
from abc import ABC, abstractmethod
from typing import List

class Window(ABC):
    @abstractmethod
    def draw(self):
        pass
    
class TestWindow(Window):
    def __init__(self):
        self.count = 0
    
    def draw(self):
        imgui.set_next_window_size((400, 400), imgui.Cond.FIRST_USE_EVER)
        imgui.begin('Application Window')
        if imgui.button("Click me!"):
            self.count += 1
        imgui.same_line()
        imgui.text(f"Clicked {self.count} times")
        imgui.end()

class App:
    def __init__(self, window: Any, renderer: GlfwRenderer):
        self.window = window
        self.renderer = renderer
        self.windows: List[Window] = [TestWindow()]
    
    def draw(self):
        for window in self.windows:
            window.draw()
