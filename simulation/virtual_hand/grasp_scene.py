"""Small procedural MuJoCo props for hand-contact demonstrations."""

OBJECT_BODY = """
    <geom name="obj_table" type="box" pos="0 0 0.280" size="0.23 0.14 0.020"
          rgba="0.30 0.34 0.40 1" friction="1.4 0.04 0.001"/>
    <body name="obj_ball_body" pos="0 -0.055 0.355">
      <freejoint name="obj_ball_free"/>
      <geom name="obj_ball" type="sphere" size="0.026" mass="0.045"
            rgba="0.95 0.25 0.18 1" friction="1.2 0.03 0.001"/>
    </body>
    <body name="obj_cube_body" pos="0.105 -0.025 0.326">
      <freejoint name="obj_cube_free"/>
      <geom name="obj_cube" type="box" size="0.026 0.026 0.026" mass="0.060"
            rgba="0.20 0.65 0.95 1" friction="1.2 0.03 0.001"/>
    </body>
    <body name="obj_cylinder_body" pos="-0.105 -0.025 0.332">
      <freejoint name="obj_cylinder_free"/>
      <geom name="obj_cylinder" type="cylinder" size="0.022 0.032" mass="0.055"
            rgba="0.95 0.72 0.18 1" friction="1.2 0.03 0.001"/>
    </body>
"""

