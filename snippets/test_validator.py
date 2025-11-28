import math
from typing import Dict, List, Tuple, Optional
from constraints import RANGES
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate

class TestValidator:
    def __init__(self, logger):
        self.log = logger
        
    def _obstacle_to_polygon(self, obs):
        """
        Convert obstacle (size + position + rotation) 
        """
        size = obs.get("size") or obs.get("dimensions")
        pos  = obs.get("position") or obs.get("pose")

        l = float(size["l"])
        w = float(size["w"])
        r = float(pos.get("r", 0))       # rotation in degrees
        x = float(pos["x"])
        y = float(pos["y"])

        # Base rectangle centered at (0, 0)
        rect = Polygon([
            (-l / 2, -w / 2),
            ( l / 2, -w / 2),
            ( l / 2,  w / 2),
            (-l / 2,  w / 2),
        ])

        # Rotate around center, then translate
        rect = rotate(rect, r, use_radians=False)
        rect = translate(rect, xoff=x, yoff=y)

        return rect

    def obstacles_overlap(self, obs1, obs2):
        """Return True if rotated obstacles overlap (interiors intersect)."""
        p1 = self._obstacle_to_polygon(obs1)
        p2 = self._obstacle_to_polygon(obs2)

        # intersects() → True even for edges touching
        # touches()     → True only when boundaries touch but no actual overlap
        return p1.intersects(p2) and not p1.touches(p2)

    def any_overlap(self, obstacles):
        """Return True if ANY pair of rotated obstacles overlap."""
        n = len(obstacles)
        for i in range(n):
            for j in range(i + 1, n):
                if self.obstacles_overlap(obstacles[i], obstacles[j]):
                    return True
        return False
    
    def check_based_and_min_height(self, obstacles, min_height=10):
        """
        Returns True if all obstacles have z=0 and h > min_height.
        Returns False otherwise.
        """
        all_on_ground = all(obs['position']['z'] == 0 for obs in obstacles)
        all_tall_enough = all(obs['size']['h'] > min_height for obs in obstacles)
        self.log.info(f"are obstacles placed on ground {all_on_ground} \n are obstacles taller than 10m {all_tall_enough}")
        return all_on_ground and all_tall_enough
    
    def check_obstacle_parameter_ranges(self, obstacles):
        """
        Checks if all parameters of all obstacles are within valid ranges.
        Returns True if all pass, otherwise False.
        """
        # Ranges
        
        for idx, obs in enumerate(obstacles):
            pos = obs.get('position', {})
            size = obs.get('size', {})
            checks = [
                ('x', pos.get('x')),
                ('y', pos.get('y')),
                ('z', pos.get('z')),
                ('l', size.get('l')),
                ('w', size.get('w')),
                ('h', size.get('h')),
                ('r', pos.get('r')),
            ]
            for name, value in checks:
                minval, maxval = RANGES[name]
                if value is None or not (minval <= value <= maxval):
                    print(f"Obstacle {idx}: Parameter '{name}' = {value} is out of range [{minval}, {maxval}]")
                    self.log.warning(f"Obstacle {idx}: Parameter '{name}' = {value} is out of range [{minval}, {maxval}]")
                    return False
        return True
    
    def out_of_range(self, value, min, max):
        return not (min <= value <= max)
    
    def rotated_extents(self, x, y, l, w, r_deg):
        """
        Axis-aligned bounds (left, right, bottom, top) of a rectangle centered at (x, y),
        with footprint l×w rotated by r_deg around its center.
        """
        th = math.radians(r_deg)
        hl, hw = l / 2.0, w / 2.0
        dx = abs(hl * math.cos(th)) + abs(hw * math.sin(th))
        dy = abs(hl * math.sin(th)) + abs(hw * math.cos(th))
        left   = x - dx
        right  = x + dx
        bottom = y - dy
        top    = y + dy
        return left, right, bottom, top

    def check_within_boundary(self, obstacles, x_min=-40.0, x_max=30.0, y_min=10.0, y_max=40.0):
        for obs in obstacles:
            x = float(obs["position"]["x"])
            y = float(obs["position"]["y"])
            r = float(obs["position"]["r"])
            l = float(obs["size"]["l"])
            w = float(obs["size"]["w"])

            left, right, bottom, top = self.rotated_extents(x,y,l,w,r)

            # Check all sides are inside bounds
            if x <= 0 and y > 25:
                if self.out_of_range(left,x_min,x_max) or self.out_of_range(top, y_min,y_max):
                    return False
            if x <= 0 and y <= 25:
                if self.out_of_range(left,x_min,x_max) or self.out_of_range(bottom, y_min,y_max):
                    return False
            if x > 0 and y > 25:
                if  self.out_of_range(right,x_min,x_max) or self.out_of_range(top, y_min,y_max):
                    return False
            if x > 0 and y <= 25:
                if self.out_of_range(right,x_min,x_max) or self.out_of_range(bottom, y_min,y_max):
                    return False
        return True


        