"""Sample dealership inventory (prices in ZAR, mileage in km)."""

# (make, model, variant, year, price, mileage, fuel, transmission, body, colour, available)
_ROWS = [
    # --- Toyota ---
    ("Toyota", "Urban Cruiser", "1.5 XR", 2021, 229900, 48000, "Petrol", "Automatic", "SUV", "White", True),
    ("Toyota", "Urban Cruiser", "1.5 XI", 2022, 249900, 31000, "Petrol", "Manual", "SUV", "Grey", True),
    ("Toyota", "RAV4", "2.0 GX", 2016, 239900, 98000, "Petrol", "Automatic", "SUV", "Silver", True),
    ("Toyota", "RAV4", "2.0 GX-R", 2018, 329900, 76000, "Petrol", "Automatic", "SUV", "Black", True),
    ("Toyota", "Corolla Cross", "1.8 XS Hybrid", 2022, 389900, 42000, "Hybrid", "Automatic", "SUV", "White", True),
    ("Toyota", "Fortuner", "2.8 GD-6 4x4", 2019, 549900, 89000, "Diesel", "Automatic", "SUV", "Grey", True),
    ("Toyota", "Starlet", "1.4 Xi", 2022, 199900, 35000, "Petrol", "Manual", "Hatchback", "Red", True),
    ("Toyota", "Yaris", "1.5 Xs", 2019, 189900, 92000, "Petrol", "Automatic", "Hatchback", "Blue", True),
    ("Toyota", "Corolla", "1.6 Prestige", 2017, 179900, 118000, "Petrol", "Manual", "Sedan", "Silver", True),
    ("Toyota", "Hilux", "2.4 GD-6 Raider", 2020, 459900, 85000, "Diesel", "Manual", "Bakkie", "White", True),
    ("Toyota", "Quantum", "2.7 GL 14-seater", 2018, 399900, 142000, "Petrol", "Manual", "Minivan", "White", False),
    # --- Volkswagen ---
    ("Volkswagen", "Polo Vivo", "1.4 Trendline", 2019, 149900, 88000, "Petrol", "Manual", "Hatchback", "White", True),
    ("Volkswagen", "Polo", "1.0 TSI Comfortline", 2020, 219900, 54000, "Petrol", "Automatic", "Hatchback", "Grey", True),
    ("Volkswagen", "Golf 7", "1.4 TSI Comfortline", 2016, 199900, 112000, "Petrol", "Automatic", "Hatchback", "Black", True),
    ("Volkswagen", "T-Cross", "1.0 TSI Comfortline", 2021, 289900, 38000, "Petrol", "Automatic", "SUV", "Orange", True),
    ("Volkswagen", "Tiguan", "1.4 TSI Trendline", 2017, 249900, 99000, "Petrol", "Automatic", "SUV", "Silver", True),
    ("Volkswagen", "Amarok", "2.0 BiTDI Highline", 2018, 429900, 120000, "Diesel", "Automatic", "Bakkie", "Grey", True),
    # --- Ford ---
    ("Ford", "Fiesta", "1.0 EcoBoost Trend", 2018, 149900, 76000, "Petrol", "Manual", "Hatchback", "Blue", True),
    ("Ford", "EcoSport", "1.0 EcoBoost Titanium", 2019, 199900, 67000, "Petrol", "Automatic", "SUV", "Red", True),
    ("Ford", "Ranger", "2.2 TDCi XLT", 2017, 319900, 135000, "Diesel", "Manual", "Bakkie", "White", True),
    ("Ford", "Ranger", "2.0 Bi-Turbo Wildtrak", 2021, 599900, 52000, "Diesel", "Automatic", "Bakkie", "Black", True),
    # --- Hyundai / Kia ---
    ("Hyundai", "Grand i10", "1.0 Motion", 2020, 139900, 41000, "Petrol", "Manual", "Hatchback", "White", True),
    ("Hyundai", "i20", "1.4 Fluid", 2019, 169900, 63000, "Petrol", "Automatic", "Hatchback", "Silver", True),
    ("Hyundai", "Creta", "1.5 Executive", 2021, 279900, 44000, "Petrol", "Automatic", "SUV", "Grey", True),
    ("Hyundai", "Tucson", "2.0 Premium", 2018, 289900, 81000, "Petrol", "Automatic", "SUV", "Black", True),
    ("Kia", "Picanto", "1.2 Street", 2021, 159900, 29000, "Petrol", "Manual", "Hatchback", "Yellow", True),
    ("Kia", "Seltos", "1.5 EX", 2021, 299900, 40000, "Petrol", "Automatic", "SUV", "White", True),
    ("Kia", "Sportage", "2.0 Ignite+", 2017, 229900, 104000, "Petrol", "Automatic", "SUV", "Blue", True),
    # --- Nissan / Suzuki / Renault ---
    ("Nissan", "Magnite", "1.0 Turbo Acenta", 2022, 209900, 27000, "Petrol", "Manual", "SUV", "Red", True),
    ("Nissan", "Qashqai", "1.2T Acenta", 2016, 189900, 109000, "Petrol", "Manual", "SUV", "Silver", True),
    ("Nissan", "Navara", "2.3D Double Cab", 2019, 389900, 95000, "Diesel", "Manual", "Bakkie", "Grey", True),
    ("Suzuki", "Swift", "1.2 GL", 2021, 179900, 33000, "Petrol", "Manual", "Hatchback", "Red", True),
    ("Suzuki", "Vitara Brezza", "1.5 GL", 2020, 219900, 58000, "Petrol", "Automatic", "SUV", "White", True),
    ("Suzuki", "Jimny", "1.5 GLX", 2022, 339900, 21000, "Petrol", "Manual", "SUV", "Green", True),
    ("Renault", "Kwid", "1.0 Dynamique", 2020, 109900, 52000, "Petrol", "Manual", "Hatchback", "Orange", True),
    ("Renault", "Duster", "1.5 dCi Dynamique", 2019, 209900, 91000, "Diesel", "Manual", "SUV", "Grey", True),
    # --- Premium / other ---
    ("Mazda", "CX-5", "2.0 Dynamic", 2019, 329900, 70000, "Petrol", "Automatic", "SUV", "Red", True),
    ("Mazda", "Mazda3", "1.6 Dynamic", 2017, 169900, 98000, "Petrol", "Manual", "Sedan", "Black", True),
    ("Haval", "Jolion", "1.5T Premium", 2022, 319900, 36000, "Petrol", "Automatic", "SUV", "White", True),
    ("BMW", "320i", "M Sport", 2017, 299900, 105000, "Petrol", "Automatic", "Sedan", "Blue", True),
    ("Mercedes-Benz", "C200", "AMG Line", 2018, 389900, 82000, "Petrol", "Automatic", "Sedan", "Silver", True),
    ("Audi", "A3", "1.4 TFSI Sportback", 2017, 209900, 96000, "Petrol", "Automatic", "Hatchback", "White", True),
    ("Volvo", "XC40", "T3 Momentum", 2020, 419900, 48000, "Petrol", "Automatic", "SUV", "Grey", True),
    ("BMW", "i3", "Range Extender", 2018, 289900, 61000, "Electric", "Automatic", "Hatchback", "Blue", True),
]

_COLUMNS = (
    "make", "model", "variant", "year", "price", "mileage",
    "fuel_type", "transmission", "body_type", "colour", "availability",
)

SAMPLE_VEHICLES: list[dict] = [dict(zip(_COLUMNS, row)) for row in _ROWS]
