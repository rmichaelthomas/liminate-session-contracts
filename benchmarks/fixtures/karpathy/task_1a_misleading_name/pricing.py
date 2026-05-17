def calculate_discount(price, quantity):
    rate = 0.08
    subtotal = price * quantity
    tax = subtotal * rate
    total = subtotal + tax
    return total


def format_price(amount):
    return f"${amount:.2f}"
