"""Build the button and grip detail scenes for the Sony DualSense still series."""

from build_macros import _macro


def build_eight_macros(source):
    """Return two portrait macro scenes sharing the original controller meshes."""
    buttons = _macro(
        source, "06 Face Buttons | Polycarbonate Macro", "06-face-buttons-macro",
        0.06, (0.019, 0.027, 0.043), 0.19,
        ((1.07, -0.48, 1.52), 33, 25, 3.43, 104, -25, 3.40, 10.0),
        (
            ("Buttons | Neutral diffusion", (-3.65, -3.05, 4.75),
             (0.86, -0.46, 1.50), 425, 2.70, 2.65, (1, 0.98, 0.94)),
            ("Buttons | Tapered cap rim", (3.15, -1.9, 2.2),
             (1.0, -0.45, 1.53), 67, 0.29, 2.2, (0.85, 0.92, 1)),
            ("Buttons | Shoulder separation", (1.7, 1.9, 4.0),
             (0.9, -0.30, 1.60), 160, 1.5, 2.8, (0.77, 0.88, 1)),
            ("Buttons | Dark inlay return", (-1.65, -3.8, 1.25),
             (0.20, -0.52, 1.20), 48, 1.8, 0.48, (0.95, 0.97, 1)),
            ("Buttons | Slate background", (-2.25, 1.6, 2.75),
             (-0.8, 0.4, 0), 84, 2.0, 1.8, (0.70, 0.82, 1)),
        ),
    )
    grip = _macro(
        source, "07 Rear Grip | Surface Macro", "07-rear-grip-macro",
        0.10, (0.023, 0.031, 0.043), 0.035,
        ((1.43, 0.48, 0.52), 153, 13, 2.16, 110, -20, 2.10, 14.0),
        (
            ("Grip | Main silk", (-3.65, -4.15, 5.4),
             (0, -0.02, 1.2), 26, 4.5, 3.0, (1, 0.976, 0.948)),
            ("Grip | Broad rear fill", (-3.05, 3.55, 4.4),
             (1.28, 0.40, 0.6), 8, 3.9, 3.7, (0.97, 0.985, 1)),
            ("Grip | Cool molded edge", (3.55, 2.5, 3.55),
             (1.20, 0.31, 0.76), 20, 1.3, 3.1, (0.79, 0.88, 1)),
            ("Grip | Grazing pattern strip", (3.68, -0.17, 1.00),
             (1.43, 0.48, 0.52), 160, 0.14, 1.15, (1, 0.98, 0.95)),
            ("Grip | Surface falloff", (0.7, -1.4, 3.4),
             (0.58, 0.33, 0), 16, 1.6, 1.4, (0.71, 0.84, 1)),
        ),
    )
    for scene in (buttons, grip):
        scene.render.resolution_x = 3072
        scene.render.resolution_y = 3840
    buttons["Visual focus"] = "Original translucent action caps and dark, uncolored glyphs"
    grip["Visual focus"] = "Original rear shell and packed controller grip relief map"
    return buttons, grip
