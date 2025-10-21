from discord import ui
import discord
from utils.language_manager import LanguageManager

class ErrorMessageView(ui.LayoutView):
    def __init__(self, *, timeout = 180, error_message: str = None):
        super().__init__(timeout=timeout)

        self.clear_items()
        container = ui.Container(
            accent_colour=discord.Color.red()
        )

        error_header = ui.TextDisplay("## Something Went Wrong!")
        error_display = ui.TextDisplay(
            error_message or "An unknown error occurred. Please try again later."
        )
        container.add_item(error_header)
        container.add_item(error_display)
        self.add_item(container)

class SuccessMessageView(ui.LayoutView):
    def __init__(self, *, timeout = 180, success_message: str = None):
        super().__init__(timeout=timeout)

        self.clear_items()
        container = ui.Container(
            accent_colour=discord.Color.green()
        )

        success_header = ui.TextDisplay("## Success!")
        success_display = ui.TextDisplay(
            success_message or "The operation was completed successfully."
        )
        container.add_item(success_header)
        container.add_item(success_display)
        self.add_item(container)

class MessageView(ui.LayoutView):
    def __init__(self, *, timeout = 180, header: str = None, message: str = None, colour: discord.Color = None):
        super().__init__(timeout=timeout)

        self.clear_items()
        container = ui.Container()

        if colour:
            container.accent_colour = colour

        if header:
            message_header = ui.TextDisplay(header)
            container.add_item(message_header)

        if message:
            message_display = ui.TextDisplay(message)
            container.add_item(message_display)

        self.add_item(container)