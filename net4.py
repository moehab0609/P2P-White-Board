import tkinter as tk
from tkinter import *
from tkinter.colorchooser import askcolor
from tkinter import ttk
import socket
import threading
import pickle

class WhiteboardPeer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = []  # List of connected peers
        self.known_peers = set()  # Set of known peers (host, port)
        self.is_running = True

        # Tkinter GUI setup
        self.current_x=0
        self.current_y=0
        self.color="black"
        self.root = tk.Tk()
        self.root.geometry("850x350+150+50")
        self.root.configure(bg="#f2f3f5")
        self.root.resizable(False,False)
        self.root.title(f"P2P Whiteboard - {host}:{port}")
        self.canvas = Canvas(self.root, width=730, height=300, bg="white",cursor="hand2")
        self.canvas.place(x=100,y=10)
        self.colors=Canvas(self.root,bg="#ffffff",width=37,height=300,bd=0)
        self.colors.place(x=30,y=10) 
        self.eraser= Button(self.root,text="clear",command=self.new_canvas,bg="#f2f3f5")
        self.eraser.place(x=30,y=320)

        self.display_pallete()
        # Event bindings
        self.canvas.bind("<B1-Motion>", self.draw)  # Mouse drag to draw
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)  # Stop drawing
        self.canvas.bind('<Button-1>',self.locate_xy)

        self.drawing = False

        # Networking in a background thread
        threading.Thread(target=self.start_server, daemon=True).start()

    def start_server(self):
        """Start the server to accept connections."""
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        print(f"Listening for connections on {self.host}:{self.port}")
        while self.is_running:
            connection, address = self.socket.accept()
            print(f"Accepted connection from {address}")
            self.connections.append(connection)
            threading.Thread(target=self.handle_client, args=(connection, address), daemon=True).start()

    def connect_to_peer(self, peer_host, peer_port):
        """Connect to an existing peer."""
        connection = socket.create_connection((peer_host, peer_port))
        self.connections.append(connection)
        self.known_peers.add((peer_host, peer_port))
        print(f"Connected to {peer_host}:{peer_port}")
        threading.Thread(target=self.handle_client, args=(connection, (peer_host, peer_port)), daemon=True).start()

    def handle_client(self, connection, address):
        """Handle incoming data from a peer."""
        while self.is_running:
            try:
                data = connection.recv(4096)
                if data:
                    message = pickle.loads(data)
                    self.process_message(message, connection)
            except (socket.error, EOFError):
                break

        print(f"Connection closed with {address}")
        connection.close()
        if connection in self.connections:
            self.connections.remove(connection)

    def process_message(self, message, sender_connection):
        """Process incoming messages and update UI or state."""
        if message["type"] == "draw_event":
            self.draw_from_network(message["data"])
            self.relay_message(message, sender_connection)
        elif message["type"] == "clear":
            # Clear the canvas locally
            self.root.after(0, self.new_canvas)
        elif message["type"] == "color_change":
            # Update the color locally
            self.root.after(0, lambda: setattr(self, "color", message["color"]))
        elif message["type"] == "peer_list":
            new_peers = message["data"]
            for peer in new_peers:
                if peer not in self.known_peers and (peer[0], peer[1]) != (self.host, self.port):
                    self.known_peers.add(peer)
                    threading.Thread(target=lambda: self.connect_to_peer(*peer), daemon=True).start()


    def relay_message(self, message, sender_connection):
        """Relay a message to all connected peers except the sender."""
        for connection in self.connections:
            if connection != sender_connection:
                try:
                    connection.sendall(pickle.dumps(message))
                except socket.error:
                    if connection in self.connections:
                        self.connections.remove(connection)

    def send_event(self, event):
        """Send drawing events to all peers."""
        message = {"type": "draw_event", "data": event}
        self.relay_message(message, None)  # Send to all peers

    def send_peer_list(self, connection):
        """Send the list of known peers to a new connection."""
        message = {"type": "peer_list", "data": list(self.known_peers)}
        try:
            connection.sendall(pickle.dumps(message))
        except socket.error:
            pass

    def draw(self, event):
        """Draw on the local canvas and broadcast the event."""
        if not self.drawing:
            self.drawing = True
            self.prev_x, self.prev_y = event.x, event.y
            return

        # Draw on local canvas
        self.canvas.create_line(self.prev_x, self.prev_y, event.x, event.y, fill=self.color, width=2)

        # Broadcast event to peers
        event_data = {"prev_x": self.prev_x, "prev_y": self.prev_y, "x": event.x, "y": event.y}
        self.send_event(event_data)

        # Update previous coordinates
        self.prev_x, self.prev_y = event.x, event.y

    def stop_draw(self, event):
        """Stop the current drawing session."""
        self.drawing = False

    def draw_from_network(self, event):
        """Draw events received from peers on the local canvas."""
        self.canvas.create_line(event["prev_x"], event["prev_y"], event["x"], event["y"], fill=self.color, width=2)

    def start_gui(self):
        """Start the Tkinter mainloop in the main thread."""
        self.root.mainloop()
    
    def show_color(self,new_color): 
        """Update the current drawing color and optionally broadcast the change."""
        self.color = new_color
        # Broadcast color change if synchronization is needed
        message = {"type": "color_change", "color": new_color}
        self.relay_message(message, None)
    def locate_xy(self,event):
        self.current_x=event.x
        self.current_y=event.y
    
    
    def display_pallete(self):
        colors = ['black', 'grey', 'brown4', 'red', 'blue', 'orange', 'yellow', 'green', 'purple']
        for i, color in enumerate(colors):
            rect_id = self.colors.create_rectangle((10, 10 + i * 30, 30, 30 + i * 30), fill=color)
            self.colors.tag_bind(rect_id, '<Button-1>', lambda event, c=color: self.show_color(c))
    def new_canvas(self):
        """Clear the canvas locally and broadcast the clear event."""
        self.canvas.delete('all')
        self.display_pallete()  # Redisplay the palette
        message = {"type": "clear"}
        self.relay_message(message, None)
# Usage Example
if __name__ == "__main__":
    # Start a peer instance
    host = input("Enter your host (e.g., 127.0.0.1): ")
    port = int(input("Enter your port (e.g., 9000): "))
    peer = WhiteboardPeer(host, port)

    # Optionally connect to an existing peer
    if input("Connect to another peer? (y/n): ").lower() == "y":
        peer_host = input("Enter peer host (e.g., 127.0.0.1): ")
        peer_port = int(input("Enter peer port (e.g., 9001): "))
        threading.Thread(target=lambda: peer.connect_to_peer(peer_host, peer_port), daemon=True).start()

    # Start the GUI
    peer.start_gui()
