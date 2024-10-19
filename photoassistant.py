#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Rsvg", "2.0")
from gi.repository import Gtk, GObject, GdkPixbuf, GLib, Gdk, Rsvg
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

        self.status_label = Gtk.Label(label="")
        grid.attach(self.status_label, 3, 1, 1, 1)

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

        # About button
        about_button = Gtk.Button(label="About")
        about_button.connect("clicked", self.on_about_button_clicked)
        hbox_controls2.pack_start(about_button, True, True, 0)                                                  

        grid.attach(hbox_controls2, 4, 0, 2, 1)

        # HBox to store buttons at upper right corner, second row
        hbox_controls3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_controls3.set_halign(Gtk.Align.FILL)  # Center align the hbox_controls

        # Cluster the Images
        cluster_button = Gtk.Button(label="Cluster Photos")
        cluster_button.connect("clicked", self.cluster)
        hbox_controls3.pack_start(cluster_button, True, True, 0)        

        #Settings Button
        settings_button=Gtk.Button(label="Settings")
        settings_button.connect("clicked",self.on_open_settings)
        hbox_controls3.pack_start(settings_button,True,True,0)                                          

        grid.attach(hbox_controls3, 4, 1, 2, 1)

        # A sidebar for further options and fine tuning adjustments could be included, consider this later
    
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
                if self.output_auto:
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
        # load images into the first thumbnail grid
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
        files = self.input_entry.get_text().split(", ")
        if not files:
            self.update_status("No images to cluster.")
            return

        # Clear the second grid before clustering (runs on main thread)
        for child in self.thumbnail_grid2.get_children():
            self.thumbnail_grid2.remove(child)

        # Update status to inform user that clustering has started
        self.update_status(f"Clustering Images...")

        # Run the clustering process in a background thread
        thread = threading.Thread(target=self.cluster_images_thread, args=(files,))
        thread.start()

    def cluster_images_thread(self, image_paths):     # this function runs in a separate thread to avoid frezing the GUI
        clusters = self.cluster_images(image_paths)

        # Pass the result back to the main thread to update the GUI
        GLib.idle_add(self.display_clusters, clusters)

    def display_clusters(self, clusters): # Updates the GUI with clustered images,runs on the main thread tho
        row = 0

        for cluster in clusters:
            # Add a horizontal separator between clusters
            if row > 0:
                separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                self.thumbnail_grid2.attach(separator, 0, row, 4, 1)
                row += 1

            for idx, image_path in enumerate(cluster):
                self.add_thumbnail(image_path, self.thumbnail_grid2, row * 4 + idx)

            row += (len(cluster) // 4) + 1  # Move to next row for new cluster

        # Update the status to inform the user clustering is done
        self.update_status(f"Clustering completed. {len(clusters)} clusters found.")

    def cluster_images(self, image_paths):
        # this funtion clusters images based on pixel similarity. Returns a list of clusters (each cluster is a list of image paths).
        def are_similar(img1, img2):
            # use basic image comparison (e.g., mean pixel difference or delta E)
            img1 = Image.open(img1).resize((200, 200)) # these values can severely slow down performance
            img2 = Image.open(img2).resize((200, 200))

            # Convert to RGB if necessary
            if img1.mode != "RGB":
                img1 = img1.convert("RGB")
            if img2.mode != "RGB":
                img2 = img2.convert("RGB")

            pixels1 = list(img1.getdata())
            pixels2 = list(img2.getdata())

            # compute the mean pixel difference or delta E
            diff = sum(get_delta_e(p1, p2) for p1, p2 in zip(pixels1, pixels2)) / len(pixels1)
            return diff < 15  # Threshold for similarity, TODO add this to settings later, scores above 10 seem to be ok

        clusters = []
        for image_path in image_paths:
            added = False
            for cluster in clusters:
                if are_similar(image_path, cluster[0]):
                    cluster.append(image_path)
                    added = True
                    break
            if not added:
                clusters.append([image_path])
        return clusters
    
    def on_open_settings(self,widget):
        # this creates a dialog window for settings
        dialog = Gtk.Dialog(title="Settings", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        # Get the content area of the dialog
        content_area = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        vbox.set_halign(Gtk.Align.CENTER)  # Center align the hbox_controls
        vbox.set_margin_top(15)            # Add top margin
        vbox.set_margin_bottom(15)         # Add bottom margin
        vbox.set_margin_start(15)          # Add left margin
        vbox.set_margin_end(15)            # Add right margin
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

    def on_toggle_auto_output_folder(self, widget):
        self.output_auto = widget.get_active()
        print(f"Automatic output folder selection: {self.output_auto}")

    def on_about_button_clicked(self, widget):
         # Create the About dialog
        about_dialog = Gtk.Dialog(title="About Photo Assistant", transient_for=self, flags=0)
        about_dialog.set_default_size(400, 400)  # Adjust size to fit the icon and text
        about_dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK)

        # Create a vertical box to hold both the icon and the text
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_halign(Gtk.Align.CENTER)  # Center align the hbox_controls
        vbox.set_margin_top(15)            # Add top margin
        vbox.set_margin_bottom(15)         # Add bottom margin
        vbox.set_margin_start(15)          # Add left margin
        vbox.set_margin_end(15)            # Add right margin

        # Load the SVG icon
        icon_path = "/app/share/icons/hicolor/scalable/apps/PLACEHOLDER"  # Update with Photo Assistant SVG icon path
        try:
            handle = Rsvg.Handle.new_from_file(icon_path)  # Load the SVG file
            # Create a pixbuf from the SVG handle
            svg_dimensions = handle.get_dimensions()
            icon_pixbuf = handle.get_pixbuf()
        
            # Create an image from the pixbuf
            icon_image = Gtk.Image.new_from_pixbuf(icon_pixbuf)
            icon_image.set_halign(Gtk.Align.CENTER)  # Center the icon
            vbox.pack_start(icon_image, False, False, 0)
        except Exception as e:
            print(f"Error loading SVG: {e}")
            # Handle error if the SVG cannot be loaded
            icon_image = Gtk.Label(label="(Error loading SVG)")
            icon_image.set_halign(Gtk.Align.CENTER)
            vbox.pack_start(icon_image, False, False, 0)

        # Create a label with information about the program
        about_label = Gtk.Label(label=(
        "\n"
        "   This program automatically sorts images and selects the best one. The use case is to remove blurry and repeated photos. \n\n "
        "   Usage:\n   "
        "    1. Select the input images.\n    "
        " \n PLACEHOLDER TEXT \n"
        "   In the Settings menu, the threshold value represents how strict the frame selection will be, i.e. higher \n     threshold values mean that only very clear frames will be selected. \n\n "
        "   Version alpha. This program comes with absolutely no warranty. Check the MIT Licence for further details.  "
        ))
        about_label.set_justify(Gtk.Justification.LEFT)
        about_label.set_halign(Gtk.Align.CENTER)

        # Add the label to the vertical box below the icon
        vbox.pack_start(about_label, True, True, 0)

        # Add the vbox to the content area of the dialog
        about_content_area = about_dialog.get_content_area()
        about_content_area.pack_start(vbox, True, True, 10)  # Add some padding for a cleaner look

        # Show all components
        about_dialog.show_all()

        # Run the dialog and wait for response
        about_dialog.run()
        about_dialog.destroy()

def main():
    app = photoassistant()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
