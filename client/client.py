import customtkinter as ctk
import requests

API_BASE = "https://rglmi1s1v8.execute-api.us-east-2.amazonaws.com/test"

ctk.set_appearance_mode("light")

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Image Color Analyzer")
        self.geometry("600x500")

        # title
        self.title_label = ctk.CTkLabel(self, text="Image Color Analyzer", font=("Arial", 24))
        self.title_label.pack(pady=20)

        # search frame
        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(pady=10)

        self.score_type = ctk.CTkOptionMenu(
            self.search_frame,
            values=["harmony", "contrast"]
        )
        self.score_type.pack(side="left", padx=10)

        self.threshold_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Threshold")
        self.threshold_entry.pack(side="left", padx=10)

        self.search_button = ctk.CTkButton(
            self.search_frame,
            text="Search",
            command=self.search_images
        )
        self.search_button.pack(side="left", padx=10)

        # results box
        self.results_box = ctk.CTkTextbox(self, width=500, height=300)
        self.results_box.pack(pady=20)

    def search_images(self):

        score_type = self.score_type.get()
        threshold = self.threshold_entry.get()

        url = f"{API_BASE}/images/search"

        params = {
            "score_type": score_type,
            "threshold": threshold
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            self.results_box.delete("1.0", "end")

            for item in data:
                self.results_box.insert(
                    "end",
                    f"{item['image_id']} | score = {list(item.values())[1]}\n"
                )

        except Exception as e:
            self.results_box.insert("end", f"Error: {e}")


app = App()
app.mainloop()