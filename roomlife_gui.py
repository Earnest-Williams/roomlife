#!/usr/bin/env python3
"""
RoomLife Tkinter GUI
A graphical user interface for the RoomLife simulation API.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from typing import Optional
from pathlib import Path

from roomlife.engine import new_game
from roomlife.api_service import RoomLifeAPI
from roomlife.io import save_state, load_state


class RoomLifeGUI:
    """Main GUI application for RoomLife simulation."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RoomLife Simulation")
        self.root.geometry("1200x800")

        # Initialize API
        self.state = new_game()
        self.api = RoomLifeAPI(self.state)

        # Subscribe to events
        self.api.subscribe_to_events(self.on_event)
        self.api.subscribe_to_state_changes(self.on_state_change)

        # Setup UI
        self.setup_ui()

        # Initial update
        self.update_display()

    def setup_ui(self):
        """Setup the user interface."""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Game", command=self.new_game)
        file_menu.add_command(label="Save Game", command=self.save_game)
        file_menu.add_command(label="Load Game", command=self.load_game)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Left panel - Status and Needs
        left_frame = ttk.Frame(main_frame, padding="5")
        left_frame.grid(row=0, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status section
        status_frame = ttk.LabelFrame(left_frame, text="Status", padding="10")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.day_label = ttk.Label(status_frame, text="Day: 1")
        self.day_label.grid(row=0, column=0, sticky=tk.W)

        self.time_label = ttk.Label(status_frame, text="Time: morning")
        self.time_label.grid(row=1, column=0, sticky=tk.W)

        self.location_label = ttk.Label(status_frame, text="Location: room_001")
        self.location_label.grid(row=2, column=0, sticky=tk.W)

        self.money_label = ttk.Label(status_frame, text="Money: £50.00")
        self.money_label.grid(row=3, column=0, sticky=tk.W)

        self.utilities_label = ttk.Label(status_frame, text="Utilities: Paid")
        self.utilities_label.grid(row=4, column=0, sticky=tk.W)

        # Needs section
        needs_frame = ttk.LabelFrame(left_frame, text="Needs", padding="10")
        needs_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.need_bars = {}
        needs = ["hunger", "fatigue", "warmth", "hygiene", "mood", "stress", "energy"]
        for i, need in enumerate(needs):
            label = ttk.Label(needs_frame, text=need.capitalize())
            label.grid(row=i, column=0, sticky=tk.W, pady=2)

            progress = ttk.Progressbar(needs_frame, length=200, mode='determinate')
            progress.grid(row=i, column=1, padx=(10, 0), pady=2)
            self.need_bars[need] = progress

        # Traits section
        traits_frame = ttk.LabelFrame(left_frame, text="Traits", padding="10")
        traits_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.trait_bars = {}
        traits = ["discipline", "confidence", "empathy", "fitness", "frugality", "curiosity", "stoicism", "creativity"]
        for i, trait in enumerate(traits):
            label = ttk.Label(traits_frame, text=trait.capitalize())
            label.grid(row=i, column=0, sticky=tk.W, pady=2)

            progress = ttk.Progressbar(traits_frame, length=200, mode='determinate')
            progress.grid(row=i, column=1, padx=(10, 0), pady=2)
            self.trait_bars[trait] = progress

        # Utilities section
        utilities_frame = ttk.LabelFrame(left_frame, text="Utilities", padding="10")
        utilities_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.utility_bars = {}
        utilities = ["power", "heat", "water"]
        for i, utility in enumerate(utilities):
            label = ttk.Label(utilities_frame, text=utility.capitalize())
            label.grid(row=i, column=0, sticky=tk.W, pady=2)

            progress = ttk.Progressbar(utilities_frame, length=200, mode='determinate')
            progress.grid(row=i, column=1, padx=(10, 0), pady=2)
            self.utility_bars[utility] = progress

        # Items section
        items_frame = ttk.LabelFrame(left_frame, text="Items at Location", padding="10")
        items_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))

        # Scrollable text for items
        self.items_text = scrolledtext.ScrolledText(items_frame, height=8, width=35, wrap=tk.WORD)
        self.items_text.pack(fill=tk.BOTH, expand=True)

        # Top right - Actions
        actions_frame = ttk.LabelFrame(main_frame, text="Available Actions", padding="10")
        actions_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))

        # Scrollable frame for actions
        actions_canvas = tk.Canvas(actions_frame, height=300)
        actions_scrollbar = ttk.Scrollbar(actions_frame, orient="vertical", command=actions_canvas.yview)
        self.actions_inner_frame = ttk.Frame(actions_canvas)

        self.actions_inner_frame.bind(
            "<Configure>",
            lambda e: actions_canvas.configure(scrollregion=actions_canvas.bbox("all"))
        )

        actions_canvas.create_window((0, 0), window=self.actions_inner_frame, anchor="nw")
        actions_canvas.configure(yscrollcommand=actions_scrollbar.set)

        actions_canvas.pack(side="left", fill="both", expand=True)
        actions_scrollbar.pack(side="right", fill="y")

        # Bottom right - Event log
        log_frame = ttk.LabelFrame(main_frame, text="Event Log", padding="10")
        log_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0), pady=(10, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.event_log = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.event_log.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Clear log button
        clear_btn = ttk.Button(log_frame, text="Clear Log", command=self.clear_log)
        clear_btn.grid(row=1, column=0, pady=(5, 0))

    def update_display(self):
        """Update all display elements with current state."""
        snapshot = self.api.get_state_snapshot()

        # Update status
        self.day_label.config(text=f"Day: {snapshot.world.day}")
        self.time_label.config(text=f"Time: {snapshot.world.slice}")
        self.location_label.config(text=f"Location: {snapshot.current_location.name}")
        self.money_label.config(text=f"Money: £{snapshot.player_money_pence / 100:.2f}")
        self.utilities_label.config(
            text=f"Utilities: {'Paid' if snapshot.utilities_paid else 'UNPAID'}"
        )

        # Update needs
        needs_dict = snapshot.needs.to_dict()
        for need, value in needs_dict.items():
            if need in self.need_bars:
                self.need_bars[need]['value'] = value

        # Update traits
        traits_dict = snapshot.traits.to_dict()
        for trait, value in traits_dict.items():
            if trait in self.trait_bars:
                self.trait_bars[trait]['value'] = value

        # Update utilities
        utilities_dict = snapshot.utilities.to_dict()
        for utility, value in utilities_dict.items():
            if utility in self.utility_bars:
                # Convert boolean to numeric value (100 = on, 0 = off)
                self.utility_bars[utility]['value'] = 100 if value else 0

        # Update items at current location
        self.items_text.delete('1.0', tk.END)
        items_at_location = self.state.get_items_at(self.state.world.location)
        if items_at_location:
            for item in items_at_location:
                # Color code based on condition
                condition_color = {
                    'pristine': '#00AA00',
                    'used': '#0066FF',
                    'worn': '#FF9900',
                    'broken': '#FF3300',
                    'filthy': '#AA0000'
                }.get(item.condition, '#000000')

                item_text = f"• {item.item_id.replace('_', ' ').title()}\n"
                item_text += f"  Condition: {item.condition} ({item.condition_value}/100)\n\n"

                start_idx = self.items_text.index(tk.END)
                self.items_text.insert(tk.END, item_text)

                # Tag the condition line with color
                lines = item_text.split(chr(10))
                tag_start = len(lines[0]) + 1  # Skip first line and newline
                tag_end = tag_start + len(lines[1])  # Add second line length
                self.items_text.tag_add(f"condition_{item.item_id}",
                                       f"{start_idx} + {tag_start}c",
                                       f"{start_idx} + {tag_end}c")
                self.items_text.tag_config(f"condition_{item.item_id}", foreground=condition_color)
        else:
            self.items_text.insert(tk.END, "No items at this location")

        # Update actions
        self.update_actions()

    def update_actions(self):
        """Update the available actions list."""
        # Clear existing buttons
        for widget in self.actions_inner_frame.winfo_children():
            widget.destroy()

        # Get available actions
        actions_response = self.api.get_available_actions()

        if not actions_response.actions:
            label = ttk.Label(self.actions_inner_frame, text="No actions available")
            label.pack(pady=5)
            return

        # Create button for each action
        for action in actions_response.actions:
            frame = ttk.Frame(self.actions_inner_frame)
            frame.pack(fill=tk.X, pady=2)

            btn = ttk.Button(
                frame,
                text=action.action_id,
                command=lambda aid=action.action_id: self.execute_action(aid)
            )
            btn.pack(side=tk.LEFT, padx=5)

            # Add description if available
            if action.description:
                desc_label = ttk.Label(frame, text=action.description, foreground="gray")
                desc_label.pack(side=tk.LEFT, padx=5)

    def execute_action(self, action_id: str):
        """Execute an action and update the display."""
        # Validate first
        validation = self.api.validate_action(action_id)

        if not validation.valid:
            self.log_message(f"❌ Action '{action_id}' is invalid: {validation.reason}")
            messagebox.showwarning("Invalid Action", validation.reason or "Action cannot be executed")
            return

        # Execute action
        result = self.api.execute_action(action_id)

        if result.success:
            self.log_message(f"✓ Executed: {action_id}")
            if result.state_changes:
                for change_key, change_value in result.state_changes.items():
                    self.log_message(f"  • {change_key}: {change_value}")
        else:
            self.log_message(f"❌ Failed: {action_id}")

        # Update display
        self.update_display()

    def on_event(self, event):
        """Callback for game events."""
        self.log_message(f"📌 Event: {event.event_id}")
        if event.params:
            # Show relevant params if present
            for key, value in event.params.items():
                self.log_message(f"  {key}: {value}")

    def on_state_change(self, state):
        """Callback for state changes."""
        # Update display on state change
        self.root.after(0, self.update_display)

    def log_message(self, message: str):
        """Add a message to the event log."""
        self.event_log.insert(tk.END, message + "\n")
        self.event_log.see(tk.END)

    def clear_log(self):
        """Clear the event log."""
        self.event_log.delete(1.0, tk.END)

    def new_game(self):
        """Start a new game."""
        if messagebox.askyesno("New Game", "Start a new game? Current progress will be lost."):
            self.state = new_game()
            self.api = RoomLifeAPI(self.state)
            self.api.subscribe_to_events(self.on_event)
            self.api.subscribe_to_state_changes(self.on_state_change)
            self.log_message("🎮 New game started")
            self.update_display()

    def save_game(self):
        """Save the current game state."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if filepath:
            try:
                save_state(self.state, Path(filepath))
                self.log_message(f"💾 Game saved to {filepath}")
                messagebox.showinfo("Save Game", f"Game saved successfully to {filepath}")
            except Exception as e:
                self.log_message(f"❌ Save failed: {e}")
                messagebox.showerror("Save Error", f"Failed to save game: {e}")

    def load_game(self):
        """Load a game state from file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if filepath:
            try:
                self.state = load_state(Path(filepath))
                self.api = RoomLifeAPI(self.state)
                self.api.subscribe_to_events(self.on_event)
                self.api.subscribe_to_state_changes(self.on_state_change)
                self.log_message(f"📂 Game loaded from {filepath}")
                self.update_display()
                messagebox.showinfo("Load Game", f"Game loaded successfully from {filepath}")
            except Exception as e:
                self.log_message(f"❌ Load failed: {e}")
                messagebox.showerror("Load Error", f"Failed to load game: {e}")


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = RoomLifeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
