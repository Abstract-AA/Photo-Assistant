#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, GdkPixbuf, GLib, Gdk
from moviepy.editor import VideoFileClip
import os
import time
import threading
from PIL import Image
from basic_colormath import get_delta_e

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS  # Ensure compatibility with Pillow 10.x

if not Gtk.init_check():
    print("Failed to initialize GTK.")
    exit(1)

class photoassistant(Gtk.Window):

    def __init__(self):
        super().__init__(title="Photo Assistant")
        self.set_border_width(10)
        self.set_default_size(1200, 600)  # Adjust width for two columns
        self.output_auto = True

        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.add(vbox)

        # Grid layout for input/output controls
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        vbox.pack_start(grid, False, False, 0)

        # Input file path
        input_label = Gtk.Label(label="Input File(s):")
        grid.attach(input_label, 0, 0, 1, 1)

        self.input_entry = Gtk.Entry(hexpand=True)
        grid.attach(self.input_entry, 1, 0, 1, 1)

        input_file_button = Gtk.Button(label="Fetch Photos")
        input_file_button.connect("clicked", self.on_select_input_file)
        grid.attach(input_file_button, 2, 0, 1, 1)

        # Output file path
        output_label = Gtk.Label(label="Output Folder:")
        grid.attach(output_label, 0, 1, 1, 1)

        self.output_entry = Gtk.Entry(hexpand=True)
        grid.attach(self.output_entry, 1, 1, 1, 1)

        output_directory_button = Gtk.Button(label="Select Output Folder")
        output_directory_button.connect("clicked", self.on_select_output_directory)
        grid.attach(output_directory_button, 2, 1, 1, 1)

        # Horizontal box to hold two scrollable windows
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(hbox, True, True, 0)

        # First scrollable window with grid for fetched images
        self.scrolled_window1 = Gtk.ScrolledWindow()
        self.scrolled_window1.set_border_width(1)
        self.scrolled_window1.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled_window1.set_vexpand(True)
        self.thumbnail_grid1 = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=5, row_spacing=5)
        self.scrolled_window1.add(self.thumbnail_grid1)
        hbox.pack_start(self.scrolled_window1, True, True, 0)

        # Second scrollable window with grid for post-treatment images
        self.scrolled_window2 = Gtk.ScrolledWindow()
        self.scrolled_window2.set_border_width(1)
        self.scrolled_window2.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled_window2.set_vexpand(True)
        self.thumbnail_grid2 = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=5, row_spacing=5)
        self.scrolled_window2.add(self.thumbnail_grid2)
        hbox.pack_start(self.scrolled_window2, True, True, 0)

        self.status_label = Gtk.Label(label="")
        vbox.pack_start(self.status_label, False, False, 0)

        # HBox to store buttons at upper right corner, first row
        hbox_controls2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_controls2.set_halign(Gtk.Align.FILL)  # Center align the hbox_controls

        # Clear all button
        clearall_button = Gtk.Button(label="Clear All Inputs")
        clearall_button.connect("clicked", self.clearall)
        hbox_controls2.pack_start(clearall_button, True, True, 0)                                                  

        grid.attach(hbox_controls2, 4, 0, 2, 1)

        # HBox to store buttons at upper right corner, second row
        hbox_controls3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_controls3.set_halign(Gtk.Align.FILL)  # Center align the hbox_controls

        # Cluster the Images
        cluster_button = Gtk.Button(label="Cluster Photos")
        cluster_button.connect("clicked", self.cluster)
        hbox_controls3.pack_start(cluster_button, True, True, 0)                                                  

        grid.attach(hbox_controls3, 4, 1, 2, 1)

        self.status_label = Gtk.Label(label="")
        grid.attach(self.status_label, 0, 5, 3, 1)

        #a sidebar for further options and fine tuning adjustments could be included, consider this later
    
    def on_select_input_file(self, widget):
        dialog = Gtk.FileChooserDialog(
        title="Select Input File(s) or Folder", parent=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.set_select_multiple(True)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_filter(self.get_image_file_filter())

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.clearall(widget)
            files = dialog.get_filenames()
            self.input_entry.set_text(", ".join(files))  # Show selected files
        
            # Set output directory based on the first selected file
            if files:
                self.input_directory = os.path.dirname(files[0])
                self.output_entry.set_text(self.input_directory)

            if all(os.path.isdir(f) for f in files):
                self.load_images_from_directory(files[0])
            else:
                self.load_images_from_files(files)

        dialog.destroy()

    def load_images_from_directory(self, directory):
        self.clearall(widget)
        # Load images from a directory
        image_paths = []
        supported_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
        for filename in os.listdir(directory):
            if filename.lower().endswith(supported_extensions):
                image_paths.append(os.path.join(directory, filename))

        self.load_images_from_files(image_paths)
    
    def load_images_from_files(self, files):
        # Load images into the first thumbnail grid
        for idx, file in enumerate(files):
            self.add_thumbnail(file, self.thumbnail_grid1, idx)

    def add_thumbnail(self, image_path, grid, idx):
        # Load image and create thumbnail
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_path)
        thumbnail = pixbuf.scale_simple(100, 100, GdkPixbuf.InterpType.BILINEAR)

        image_widget = Gtk.Image.new_from_pixbuf(thumbnail)
        row = idx // 4  # 4 images per row
        col = idx % 4
        grid.attach(image_widget, col, row, 1, 1)
        grid.show_all()
        
    def update_status(self, message):
        GLib.idle_add(self.status_label.set_text, message)

    def get_image_file_filter(self):
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Image Files")
        file_filter.add_mime_type("image/jpeg")
        file_filter.add_mime_type("image/png")
        file_filter.add_mime_type("image/gif")
        file_filter.add_pattern("*.jpg")
        file_filter.add_pattern("*.jpeg")
        file_filter.add_pattern("*.png")
        file_filter.add_pattern("*.gif")
        return file_filter

    def on_select_output_directory(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Select Output Directory", parent=self, action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.output_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def clearall(self,widget):
        self.input_entry.set_text("")
        self.output_entry.set_text("")

        for child in self.thumbnail_grid1.get_children():
            self.thumbnail_grid1.remove(child)
        for child in self.thumbnail_grid2.get_children():
            self.thumbnail_grid2.remove(child)

    def cluster(self, widget):
       pass
    
    def on_open_settings(self,widget):
        # this creates a dialog window for settings
        dialog = Gtk.Dialog(title="Settings", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        # Get the content area of the dialog
        content_area = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        vbox.set_halign(Gtk.Align.CENTER)  # Center align the hbox_controls
        content_area.pack_start(vbox, False, False, 0)
        dialog.set_default_size(420, 180)

        # Create the grid
        grid2 = Gtk.Grid()
        grid2.set_column_homogeneous(False)
        grid2.set_column_spacing(10)
        grid2.set_row_spacing(10)
        vbox.pack_start(grid2, True, True, 0)

        # Label for the output folder
        autoassignfoldercb_label = Gtk.Label(label="For saving Files:")
        grid2.attach(autoassignfoldercb_label, 0, 0, 1, 1)  # Left column (0), top row (0)

        # Checkbox to set output folder
        self.autoassignfoldercb = Gtk.CheckButton(label="Automatically set input folder as output folder")
        self.autoassignfoldercb.set_active(self.output_auto)
        self.autoassignfoldercb.connect("toggled", self.on_toggle_auto_output_folder)
        grid2.attach(self.autoassignfoldercb, 1, 0, 1, 1)  # Right column (1), same row (0)

        # Show the dialog with its contents
        dialog.show_all()

        # Wait for user response (OK or Cancel)
        response = dialog.run()

        dialog.destroy()

    #def on_toggle_auto_output_folder(self, widget):
        #self.output_auto = widget.get_active()
        #print(f"Automatic output folder selection: {self.output_auto}")

def main():
    app = photoassistant()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
