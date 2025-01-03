import tkinter as tk
from tkinter import *
import socket
import threading
import pickle


class WhiteboardPeer:
    def __init__(self, host, port, user_name):
        self.host = host
        self.port = port
        self.user_name = user_name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = []
        self.is_running = True

        # Tkinter GUI setup
        self.color = "black"
        self.root = tk.Tk()
        self.root.geometry("850x400+150+50")
        self.root.configure(bg="#f2f3f5")
        self.root.resizable(True, True)
        self.root.title(f"P2P Whiteboard - {host}:{port}")

        # Canvas
        self.canvas = Canvas(self.root, width=730, height=300, bg="white", cursor="hand2", relief="groove", bd=2)
        self.canvas.place(x=100, y=10)

        # Color Palette
        self.colors = Canvas(self.root, bg="#ffffff", width=37, height=300, bd=0, relief="flat")
        self.colors.place(x=30, y=10)

        # Buttons
        self.eraser = Button(self.root, text="Clear", command=self.clear_canvas, bg="#f2f3f5", fg="#444", font=("Arial", 10, "bold"), relief="raised")
        self.eraser.place(x=30, y=320)

        self.connect_button = Button(self.root, text="Connect to Peer", command=self.open_connect_dialog, bg="#0078D7", fg="white", font=("Arial", 10, "bold"), relief="raised")
        self.connect_button.place(x=700, y=320)

        # Event Bindings
        self.display_palette()
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind('<Button-1>', self.locate_xy)

        # Networking thread
        threading.Thread(target=self.start_server, daemon=True).start()

    def open_connect_dialog(self):
        dialog = Toplevel(self.root)
        dialog.title("Connect to Peer")
        dialog.geometry("350x200")
        dialog.configure(bg="#f2f3f5")

        Label(dialog, text="Peer Host:", bg="#f2f3f5", font=("Arial", 10)).grid(row=0, column=0, pady=10, padx=10, sticky="e")
        peer_host_entry = Entry(dialog, width=25, font=("Arial", 10))
        peer_host_entry.grid(row=0, column=1, pady=10, padx=10)

        Label(dialog, text="Peer Port:", bg="#f2f3f5", font=("Arial", 10)).grid(row=1, column=0, pady=10, padx=10, sticky="e")
        peer_port_entry = Entry(dialog, width=25, font=("Arial", 10))
        peer_port_entry.grid(row=1, column=1, pady=10, padx=10)

        def connect_to_peer():
            peer_host = peer_host_entry.get()
            peer_port = int(peer_port_entry.get())
            threading.Thread(target=lambda: self.connect_to_peer(peer_host, peer_port), daemon=True).start()
            dialog.destroy()

        Button(dialog, text="Connect", command=connect_to_peer, bg="#0078D7", fg="white", font=("Arial", 10, "bold"), relief="raised").grid(row=2, column=0, columnspan=2, pady=20)

    def start_server(self):
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"Listening on {self.host}:{self.port}")
        while self.is_running:
            connection, address = self.socket.accept()
            self.connections.append(connection)
            threading.Thread(target=self.handle_client, args=(connection,), daemon=True).start()

    def connect_to_peer(self, peer_host, peer_port):
        connection = socket.create_connection((peer_host, peer_port))
        self.connections.append(connection)
        threading.Thread(target=self.handle_client, args=(connection,), daemon=True).start()

    def handle_client(self, connection):
        while self.is_running:
            try:
                data = connection.recv(4096)
                if data:
                    message = pickle.loads(data)
                    self.process_message(message, connection)
            except (socket.error, EOFError):
                break
        connection.close()

    def process_message(self, message, sender_connection):
        if message["type"] == "draw_event":
            self.root.after(0, self.draw_from_network, message["data"])
        elif message["type"] == "clear":
            self.root.after(0, self.clear_canvas, False)
        elif message["type"] == "color_change":
            self.root.after(0, lambda: setattr(self, "color", message["color"]))

        self.relay_message(message, sender_connection)

    def relay_message(self, message, sender_connection):
        for connection in self.connections:
            if connection != sender_connection:
                try:
                    connection.sendall(pickle.dumps(message))
                except socket.error:
                    self.connections.remove(connection)

    def draw(self, event):
        self.canvas.create_line(self.prev_x, self.prev_y, event.x, event.y, fill=self.color, width=2)
        event_data = {
            "prev_x": self.prev_x,
            "prev_y": self.prev_y,
            "x": event.x,
            "y": event.y,
            "user_name": self.user_name,
        }
        self.relay_message({"type": "draw_event", "data": event_data}, None)
        self.prev_x, self.prev_y = event.x, event.y

        self.display_name(event.x, event.y, self.user_name)

    def draw_from_network(self, event):
        self.canvas.create_line(event["prev_x"], event["prev_y"], event["x"], event["y"], fill=self.color, width=2)
        self.display_name(event["x"], event["y"], event["user_name"])

    def locate_xy(self, event):
        self.prev_x, self.prev_y = event.x, event.y

    def display_palette(self):
        colors = ['black', 'grey', 'brown4', 'red', 'blue', 'orange', 'yellow', 'green', 'purple']
        for i, color in enumerate(colors):
            rect = self.colors.create_rectangle((10, 10 + i * 30, 30, 30 + i * 30), fill=color, outline="grey")
            self.colors.tag_bind(rect, '<Button-1>', lambda event, c=color: self.change_color(c))

    def change_color(self, new_color):
        self.color = new_color
        self.relay_message({"type": "color_change", "color": new_color}, None)

    def clear_canvas(self, broadcast=True):
        self.canvas.delete('all')
        self.display_palette()
        if broadcast:
            threading.Thread(target=lambda: self.relay_message({"type": "clear"}, None), daemon=True).start()

    def display_name(self, x, y, name):
        self.canvas.delete("name_tag")
        self.canvas.create_text(x + 15, y - 10, text=name, fill=self.color, font=("Arial", 10), tags="name_tag")

    def start_gui(self):
        self.root.mainloop()


def show_input_dialog():
    input_root = tk.Tk()
    input_root.title("Enter Details")
    input_root.geometry("350x200")
    input_root.configure(bg="#f2f3f5")

    Label(input_root, text="Host:", bg="#f2f3f5", font=("Arial", 10)).grid(row=0, column=0, pady=10, padx=10, sticky="e")
    host_entry = Entry(input_root, width=25, font=("Arial", 10))
    host_entry.grid(row=0, column=1)

    Label(input_root, text="Port:", bg="#f2f3f5", font=("Arial", 10)).grid(row=1, column=0, pady=10, padx=10, sticky="e")
    port_entry = Entry(input_root, width=25, font=("Arial", 10))
    port_entry.grid(row=1, column=1)

    Label(input_root, text="Name:", bg="#f2f3f5", font=("Arial", 10)).grid(row=2, column=0, pady=10, padx=10, sticky="e")
    name_entry = Entry(input_root, width=25, font=("Arial", 10))
    name_entry.grid(row=2, column=1)

    def submit_details():
        host = host_entry.get()
        port = int(port_entry.get())
        name = name_entry.get()
        input_root.destroy()
        peer = WhiteboardPeer(host, port, name)
        peer.start_gui()

    Button(input_root, text="Submit", command=submit_details, bg="#0078D7", fg="white", font=("Arial", 10, "bold"), relief="raised").grid(row=3, column=0, columnspan=2, pady=20)

    input_root.mainloop()


if __name__ == "__main__":
    show_input_dialog()
