
from flask import Flask, request, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ashna Restaurant</title>

    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            background: #fff8ef;
            color: #333;
        }

        header {
            background: #713b22;
            color: white;
            text-align: center;
            padding: 35px;
        }

        nav {
            background: #38251b;
            padding: 15px;
            text-align: center;
        }

        nav a {
            color: white;
            text-decoration: none;
            margin: 15px;
        }

        section {
            max-width: 650px;
            margin: 25px auto;
            padding: 25px;
            background: white;
            border-radius: 12px;
        }

        .food {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }

        input, button {
            width: 100%;
            padding: 12px;
            margin-top: 10px;
            box-sizing: border-box;
        }

        button {
            background: #713b22;
            color: white;
            border: none;
            cursor: pointer;
        }

        .message {
            color: green;
            font-weight: bold;
        }

        footer {
            background: #38251b;
            color: white;
            text-align: center;
            padding: 20px;
        }
    </style>
</head>

<body>

<header>
    <h1>Ashna Restaurant</h1>
    <p>Fresh Food, Great Taste!</p>
</header>

<nav>
    <a href="#home">Home</a>
    <a href="#menu">Menu</a>
    <a href="#booking">Book a Table</a>
</nav>

<section id="home">
    <h2>Welcome to Ashna Restaurant</h2>
    <p>Enjoy delicious meals prepared with love.
       We are happy to serve you!</p>
</section>

<section id="menu">
    <h2>Our Menu</h2>
    <div class="food">Chicken and Chips - KSh 500</div>
    <div class="food">Pilau - KSh 250</div>
    <div class="food">Beef Burger - KSh 400</div>
    <div class="food">Tea - KSh 50</div>
</section>

<section id="booking">
    <h2>Book a Table</h2>

    {% if message %}
        <p class="message">{{ message }}</p>
    {% endif %}

    <form method="POST">
        <label>Your Name</label>
        <input type="text" name="name"
               placeholder="Enter your name" required>

        <label>Booking Date</label>
        <input type="date" name="date" required>

        <label>Number of Guests</label>
        <input type="number" name="guests"
               min="1" placeholder="Number of guests" required>

        <button type="submit">Book Now</button>
    </form>
</section>

<footer>
    <p>Copyright 2026 Ashna Restaurant</p>
</footer>

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    message = ""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        date = request.form.get("date", "").strip()
        guests = request.form.get("guests", "").strip()

        if name and date and guests:
            message = (
                f"Thank you, {name}! Your booking request "
                f"for {guests} guest(s) on {date} has been received."
            )
        else:
            message = "Please fill in all the details."

    return render_template_string(HTML, message=message)


if __name__ == "__main__":
    app.run(debug=True)
