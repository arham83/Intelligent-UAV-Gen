import re
import os
import yaml
import shutil
import csv
import pyulog
import shutil
from pyulog import ULog
from pathlib import Path
import json
import hashlib
import pandas as pd
from aerialist.px4.obstacle import Obstacle


class Helper:
    
    @staticmethod
    def to_px4_obstacles(obstacles_data):
        """
        Convert list of obstacle dicts (from YAML) into aerialist Obstacle objects.
        Assumes the YAML is valid and all fields are present.
        """
        print(f"YAML contains {len(obstacles_data)} obstacles.")

        obstacles = []
        for idx, o in enumerate(obstacles_data):
            size_dict = o["size"]
            pos_dict  = o["position"]

            size = Obstacle.Size(
                l=float(size_dict["l"]),
                w=float(size_dict["w"]),
                h=float(size_dict["h"]),
            )
            position = Obstacle.Position(
                x=float(pos_dict["x"]),
                y=float(pos_dict["y"]),
                z=float(pos_dict["z"]),  
                r=float(pos_dict["r"]),
            )

            obstacle = Obstacle(size, position)
            obstacles.append(obstacle)

        return obstacles
    
    @staticmethod
    def get_hash(test_case):
        # Convert test case to canonical JSON (sorted keys for consistency)
        canonical = json.dumps(test_case, sort_keys=True)
        # Hash using SHA256 (or MD5 if you prefer)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    @staticmethod
    def load_config(config_path: str) -> dict:
        """
        Load a YAML configuration file and return its contents as a dictionary.
        """
        with open(config_path, 'r', encoding='utf-8') as yf:
            data = yaml.safe_load(yf)

        return str(data["obstacles"])
    
    @staticmethod
    def parse_response(raw_text: str) -> str:
        """
        Extracts YAML content enclosed in ```yaml ... ``` or ``` ... ```
        and returns it as a string.
        """
        pattern = r"```(?:yaml)?(.*?)```"
        match = re.search(pattern, raw_text, re.DOTALL)

        if match:
            yaml_content = match.group(1).strip()
        else:
            # fallback if no markdown fences are found
            yaml_content = raw_text.strip()

        return yaml.safe_load(yaml_content)
    
    @staticmethod
    def write_yaml(base_seed, parsed_data, output_path) -> Path:
        """
        Extracts YAML content enclosed in ```yaml ... ``` or ``` ... ```
        and writes it to a .yaml file.
        """
        with open(base_seed, 'r', encoding='utf-8') as bs:
            base_data = yaml.safe_load(bs)
        
        base_data["simulation"]["obstacles"] = parsed_data['obstacles']
        # Write validated YAML back to file (pretty formatted)
        output_path = Path(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(base_data, f, sort_keys=False, allow_unicode=True)

        print(f"YAML extracted and written to {output_path.resolve()}")
        return output_path

    @staticmethod
    def del_file(file_path):
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"{file_path} deleted successfully.")
        else:
            print(f"{file_path} does not exist.")
            
    @staticmethod        
    def move_file(source_file: str, destination_dir: str, new_name: str = None) -> None:
        """
        Move a single file (source_file) to destination_dir.
        If new_name is provided, rename it but keep the original file extension.
        If new_name is None, keep the same name.
        """
        # Validate source file
        if not os.path.isfile(source_file):
            print(f"Source file does not exist: {source_file}")
            return
        os.makedirs(destination_dir, exist_ok=True)
        _, ext = os.path.splitext(source_file)
        if new_name is None:
            new_name = os.path.basename(source_file)
        else:
            new_name = f"{new_name}{ext}"  # Keep the same extension
        destination_path = os.path.join(destination_dir, new_name)
        shutil.move(source_file, destination_path)
        print(f"Moved file to: {destination_path}")
        
    @staticmethod
    def copy_file(source_file: str, destination_dir: str, new_name: str = None) -> None:
        """
        Copy a single file (source_file) to destination_dir.
        If new_name is provided, rename it but keep the original file extension.
        If new_name is None, keep the same name.
        """
        if not os.path.isfile(source_file):
            print(f"Source file does not exist: {source_file}")
            return
        os.makedirs(destination_dir, exist_ok=True)
        _, ext = os.path.splitext(source_file)
        if new_name is None:
            new_name = os.path.basename(source_file)
        else:
            new_name = f"{new_name}{ext}"  # Preserve original extension
        destination_path = os.path.join(destination_dir, new_name)
        shutil.copy2(source_file, destination_path)
        print(f"Copied file to: {destination_path}")
        
    @staticmethod
    def write_csv(col, row, csv_path):
        """Append a single row to the fitness CSV file."""
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            # write header only once
            if not file_exists:
                writer.writerow(col)
            writer.writerow(row)

    @staticmethod
    def get_config_info(config_path):
        with open(config_path, 'r', encoding='utf-8') as yf:
            data = yaml.safe_load(yf)
            
        return {
            "obs1_size": str(data['obstacles'][0]['size']),
            "obs1_position": str(data['obstacles'][0]['position']),
            "obs2_size": str(data['obstacles'][1]['size']),
            "obs2_position": str(data['obstacles'][1]['position'])
        }
    
    @staticmethod
    def get_config_info1(config_path):
        with open(config_path, 'r', encoding='utf-8') as yf:
            data = yaml.safe_load(yf)
        
        return {
            "obs1_size": str(data[0]['size']),
            "obs1_position": str(data[0]['position']),
            "obs2_size": str(data[1]['size']),
            "obs2_position": str(data[1]['position'])
        }
        
    @staticmethod
    def read_ulg(log_file, store_space):
        log = pyulog.ULog(log_file)

        data_list = log.data_list

        vehicle_position_data = log.get_dataset('vehicle_local_position')

        previous_timestamp = None

        if len(vehicle_position_data.data['timestamp']) < store_space:
            time_interval = 1

        else:
            time_interval = len(vehicle_position_data.data['timestamp']) // store_space

        content = ""

        for timestamp, x, y, z in zip(vehicle_position_data.data['timestamp'],
                                    vehicle_position_data.data['x'],
                                    vehicle_position_data.data['y'],
                                    vehicle_position_data.data['z']):
            if previous_timestamp is None or timestamp - previous_timestamp >= time_interval * 1e6:
                content += f"Timestamp: {timestamp}, X: {x}, Y: {y}, Z: {z} \n"
                previous_timestamp = timestamp

        return content
    
    @staticmethod
    def get_flight_time(ulg_path):
        ulog = ULog(ulg_path)

        # ULog timestamps are in microseconds
        start_us = ulog.start_timestamp
        end_us = ulog.last_timestamp

        duration_s = (end_us - start_us) / 1e6  # convert to seconds
        return duration_s

    @staticmethod
    def get_trajectory_file_path(results_dir: Path, run_id: str) -> Path:
        ulg_files = sorted(results_dir.rglob(f"*iter{run_id}*.ulg"), key=os.path.getmtime)
        return ulg_files[-1] if ulg_files else None
    
    @staticmethod
    def best_worse_fitness(file_path: str):
        df = pd.read_csv(file_path)
        max_row = df.loc[df['distance'].idxmax()]
        min_row = df.loc[df['distance'].idxmin()]
        
        dict = {
            'worse_test_case': {
                'distance': max_row['distance'],
                'obstacle1':
                {
                    'size': max_row['obs1-size'],
                    'position': max_row['obs1-position']
                },
                'obstacle2':
                {
                    'size': max_row['obs2-size'],
                    'position': max_row['obs2-position']
                }
            },
            'best_test_case': {
                'distance': min_row['distance'], 
                'obstacle1':
                {
                    'size': min_row['obs1-size'],
                    'position': min_row['obs1-position']
                },
                'obstacle2':
                {
                    'size': min_row['obs2-size'],
                    'position': min_row['obs2-position']
                }
            }
        }
        if len(df) == 1:
            number = True
        else:
            number = False
        return number, str(dict)