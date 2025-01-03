import tkinter as tk
from tkinter import *
import socket
import threading
import pickle


class WhiteboardPeer:
    def __init__(self, host, port, user_name):
        self.host = host
        self.port = port
        self.user_name = user_name  # Add user name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = []
        self.is_running = True

        # Tkinter GUI setup
        self.color = "black"
        self.root = tk.Tk()
        self.root.geometry("850x350+150+50")
        self.root.configure(bg="#f2f3f5")
        self.root.resizable(False, False)
        self.root.title(f"P2P Whiteboard - {host}:{port}")
        self.canvas = Canvas(self.root, width=730, height=300, bg="white", cursor="hand2")
        self.canvas.place(x=100, y=10)
        self.colors = Canvas(self.root, bg="#ffffff", width=37, height=300, bd=0)
        self.colors.place(x=30, y=10)
        self.eraser = Button(self.root, text="clear", command=self.clear_canvas, bg="#f2f3f5")
        self.eraser.place(x=30, y=320)

        self.display_palette()
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind('<Button-1>', self.locate_xy)

        # Networking thread
        threading.Thread(target=self.start_server, daemon=True).start()

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

        # Relay the message to other peers
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

        # Display the user's name
        self.display_name(event.x, event.y, self.user_name)

    def draw_from_network(self, event):
        self.canvas.create_line(event["prev_x"], event["prev_y"], event["x"], event["y"], fill=self.color, width=2)
        self.display_name(event["x"], event["y"], event["user_name"])

    def locate_xy(self, event):
        self.prev_x, self.prev_y = event.x, event.y

    def display_palette(self):
        colors = ['black', 'grey', 'brown4', 'red', 'blue', 'orange', 'yellow', 'green', 'purple']
        for i, color in enumerate(colors):
            rect = self.colors.create_rectangle((10, 10 + i * 30, 30, 30 + i * 30), fill=color)
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


if __name__ == "__main__":
    host = input("Enter your host (e.g., 127.0.0.1): ")
    port = int(input("Enter your port (e.g., 9000): "))
    user_name = input("Enter your name: ")
    peer = WhiteboardPeer(host, port, user_name)

    if input("Connect to another peer? (y/n): ").lower() == "y":
        peer_host = input("Enter peer host (e.g., 127.0.0.1): ")
        peer_port = int(input("Enter peer port (e.g., 9001): "))
        threading.Thread(target=lambda: peer.connect_to_peer(peer_host, peer_port), daemon=True).start()

    peer.start_gui()
