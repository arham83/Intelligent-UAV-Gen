import math
from typing import Dict, List, Tuple, Optional
from constraints import RANGES

class TestValidator:
    def __init__(self, logger):
        self.log = logger
        
    def _extract_box(self, obs):
        """Normalize obstacle schema and extract position + size fields."""
        size = obs.get("size") or obs.get("dimensions")
        pos = obs.get("position") or obs.get("pose")
        if size is None or pos is None:
            self.log.error(f"Invalid obstacle schema: expected keys 'size' or 'dimensions' and 'position'.")
            raise KeyError(f"Invalid obstacle schema: expected keys 'size' or 'dimensions' and 'position'.")

        return {
            "x": float(pos.get("x", 0.0)),
            "y": float(pos.get("y", 0.0)),
            "z": float(pos.get("z", 0.0)),
            "l": float(size.get("l", 0.0)),
            "w": float(size.get("w", 0.0)),
            "h": float(size.get("h", 0.0)),
        }

    def is_overlapping(self, obs1, obs2):
        """Check simple AABB overlap (axis-aligned bounding boxes)."""
        key_map = {"x": "l", "y": "w", "z": "h"}

        c1 = self._extract_box(obs1)
        c2 = self._extract_box(obs2)

        for axis in ["x", "y", "z"]:
            half1 = c1[key_map[axis]] / 2
            half2 = c2[key_map[axis]] / 2
            if abs(c1[axis] - c2[axis]) > (half1 + half2):
                return False  # separated along this axis
        return True  # overlap in all axes

    def any_overlap(self, obstacles):
        """Return True if any pair of obstacles overlap."""
        n = len(obstacles)
        for i in range(n):
            for j in range(i + 1, n):
                if self.is_overlapping(obstacles[i], obstacles[j]):
                    print(f"Obstacles {i} and {j} overlap.")
                    try:
                        self.log.info(f"Obstacles {i} and {j} overlap.")
                    except NameError:
                        pass  # if log isn't defined
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


        