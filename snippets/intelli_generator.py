import os
import shutil
import yaml
from pathlib import Path
from aerialist.px4.aerialist_test import AerialistTest
from testcase import TestCase
from seed_generator import SeedGenerator
from gen_mutation import GenerateMutation
from utils.helper import Helper

if os.path.exists("temp") and os.path.isdir("temp"):
    shutil.rmtree("temp")
if os.path.exists("seeds") and os.path.isdir("seeds"):
    shutil.rmtree("seeds")  
    
class IntelliGen():
    def __init__(self, logger, case_study):
        self.log = logger
        os.makedirs("soi", exist_ok=True) 
        os.makedirs("temp", exist_ok=True)
        os.makedirs("gen_config", exist_ok=True)
        self.case_study = case_study
        self.soi = self.init_soi()
        self.seed_gen = SeedGenerator(logger, self.soi, "seeds")
        self.mutator = GenerateMutation(logger, case_study, self.soi)
    
    def init_soi(self):
        """
        Will init the SOI path of the flight
        """
        test = TestCase(
            AerialistTest.from_yaml(self.case_study),
            Helper.to_px4_obstacles([])  # will be empty
        )
        _ , path = test.execute()
        self.log.info(f"SOI_path:{path}")
        Helper.copy_file(path, "soi", "soi")
        img_path = test.plot()
        self.log.info(f"SOI image stored at following path: {img_path}")
        soi = Helper.read_ulg("soi/soi.ulg", 30)
        self.log.info(f"co-ordinates of the SOI: {img_path}")
        return soi

    def run(self, budget):
        iteration = 0
        seed_iter = 0
        test_dir = set()
        test_cases = []
        col = ["Iteration", "distance", "time", "obs1-size", "obs1-position", "obs2-size", "obs2-position"]

        # Generate the seeds
        seeds_yaml, seeds_df, uti_budget = self.seed_gen.get_seeds(self.case_study, test_cases)
        
        # run Simulation
        while (iteration <= (budget -uti_budget)):
            sel_yaml = seeds_yaml[seed_iter]
            print(f"Selected Seed: {sel_yaml}")
            self.log.info(f"Selected Seed: {sel_yaml}")
            row = seeds_df[seeds_df["yaml_path"].str.strip() == sel_yaml]
            Helper.copy_file(row["yaml_path"].iloc[0], "temp", "mission")
            Helper.copy_file(row["ulg_path"].iloc[0], "temp", "trajectory")
            Helper.write_csv(col, [iteration, row["distance"].iloc[0], row["time"].iloc[0], row["obs1-size"].iloc[0], row["obs1-position"].iloc[0], row["obs2-size"].iloc[0], row["obs2-position"].iloc[0]],f"results.csv")
            iteration +=1
            for i in range(7):
                test_path = self.mutator.generate_mutated_obstacles_config(
                    "temp/trajectory.ulg",
                    "temp/mission.yaml",
                    test_dir,
                    iter=iteration,
                )
                Helper.copy_file(test_path, "temp", "mission") 
                with open(test_path, 'r', encoding='utf-8') as bs:
                    base_data = yaml.safe_load(bs)
                obstacles = base_data["obstacles"]
                test = TestCase(AerialistTest.from_yaml(self.case_study), Helper.to_px4_obstacles(obstacles))
                _, ulg_path = test.execute()
                Helper.copy_file(ulg_path, "temp", "trajectory")
                distances = test.get_distances()
                img_path = test.plot()
                self.log.info(f"Trajectory of Mutated Config stored at following path: {img_path}")
                val = Helper.get_config_info(test_path)
                if min(distances):
                    test_cases.append(test)
                Helper.write_csv(col, [iteration, min(distances), Helper.get_flight_time(ulg_path), val['obs1_size'], val['obs1_position'],val['obs2_size'], val['obs2_position']],f"results.csv")
                iteration +=1
                if min(distances) > 1.5:
                    break
            
            seed_iter +=1
            if seed_iter == 6:
                seed_iter = 0

        return test_cases

from utils.logger import LoggerManager
logger = LoggerManager(name='UAV Generator',log_dir='logs', level='INFO').get_logger()

if __name__ == "__main__":
    gen = IntelliGen(logger, "case_studies/mission2.yaml", 65)
    gen.run()