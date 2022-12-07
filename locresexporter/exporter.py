import os
import csv
import json
import subprocess

# Paths and filenames constants
PACKAGE_ROOT = os.path.join(__file__, "..", "..")
LOCRES_CONFIG = "locres_config.json"
VALORANT_PATH = "D:\\Games\\Riot Games\\VALORANT\\"
RELATIVE_LOCRES_PAK = os.path.normpath("\\live\\ShooterGame\\Content\\Paks\\{pak_language}_Text-WindowsClient.pak")


class LocresExporter:
    # Wrapper class for the exporting configuration
    def __init__(self, game_path, pak_language, folder_language):
        self.valorant_exe = game_path
        self.pak_language = pak_language
        self.folder_language = folder_language
        self.config = load_config()
        self.normalize_paths()

    def get_aes_key(self):
        # Read the AES key from the provided raw text file
        with open(self.config["aes_path"], "rt") as aes_file:
            return str.encode(aes_file.read())

    def apply_language_to_path(self, path):
        return path.replace("{pak_language}", self.pak_language)\
            .replace("{folder_language}", self.folder_language)

    def export_locres(self, locres_pak_path):
        locres_pak_path = self.apply_language_to_path(locres_pak_path)
        # Execute QuickBMS command, redirecting input to the pipe
        exporter_process = subprocess.Popen([self.config["quickbms_path"], self.config["ut4_path"],
                                             locres_pak_path, self.config["working_path"]],
                                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        # Pass the AES key to the pipe
        exporter_process.communicate(self.get_aes_key())
        exporter_process.wait()

    def locres_to_csv(self):
        # Run locres2csv
        locres_path = os.path.join(self.config["working_path"], "ShooterGame", "Content", "Localization",
                                   "Game", "{folder_language}", "Game.locres")
        locres_path = self.apply_language_to_path(locres_path)
        csv_path = os.path.join(self.config["working_path"], "ShooterGame", "Content", "Localization",
                                "Game", "{folder_language}", "Game.csv")
        csv_path = self.apply_language_to_path(csv_path)
        parser_process = subprocess.Popen([self.config["ul_path"], "export", locres_path, "-o", csv_path],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        parser_process.wait()
        os.remove(locres_path)

    def normalize_paths(self):
        # Simple path normalization
        for path, value in self.config.items():
            self.config[path] = os.path.normpath(os.path.abspath(value))

    def csv_to_json(self, json_path, force_overwrite=False, sort_keys=False):
        # Parse the CSV file to JSON
        csv_path = os.path.join(self.config["working_path"], "ShooterGame", "Content", "Localization",
                                "Game", "{folder_language}", "Game.csv")
        csv_path = self.apply_language_to_path(csv_path)
        with open(csv_path, "rt", encoding="utf-8") as csv_locres:
            # Open the CSV file and create a temporary dictionary
            csv_read = csv.DictReader(csv_locres, delimiter=",")
            json_dict = {}
            for index, line in enumerate(csv_read):
                # Begin recursion to place the line being read
                LocresExporter.__add_child(json_dict, line["key"].replace("KAY/O", "KAYO").split("/"), line["source"])

            # Dump the temporary dictionary
            self.__begin_json_parse_dump(json_path, json_dict, force_overwrite, sort_keys)
            self.__archive_json(json_dict)
        # Remove CSV file
        os.remove(csv_path)

    @staticmethod
    def __add_child(curr_dict, remaining_childs, child_contents):
        # If this is the last key in the path to the contents
        if len(remaining_childs) == 1:
            curr_dict[remaining_childs[0]] = child_contents
        # There are superkeys left to complete the path to the contents
        else:
            # Get or create the path currently being completed
            next_dict = curr_dict.get(remaining_childs[0], {})
            # Assign the reference to the next dictionary in case it did not exist
            curr_dict[remaining_childs[0]] = next_dict
            # Continue the recursion with one less remaining superkey
            LocresExporter.__add_child(next_dict, remaining_childs[1:], child_contents)

    def get_game_version(self, game_path):
        # Get the version of the game from which the Locres is being extracted
        # Read the executable as bytes
        with open(game_path, 'rb') as game_file:
            # Find the sequence of bytes and extract relevant part
            client_ver_hex = game_file.read().hex().split('2b002b0041007200650073002d0043006f00720065002b00')[1][0:192]
            # Transform bytes into a readable list of strings
            client_ver_list = list(filter(None, bytes.fromhex(client_ver_hex).decode('utf-16-le').split('\x00')))
            # Compose the version string
            return self.pak_language + '-' + client_ver_list[0] + '-' + client_ver_list[2] + '-' + \
                   client_ver_list[3].rsplit('.')[-1].lstrip('0')

    def apply_game_version_to_path(self, game_path, json_path):
        # Replace {game_version} keyword with current version
        game_version = self.get_game_version(game_path)
        return json_path.replace("{game_version}", game_version)

    @staticmethod
    def __begin_json_parse_dump(json_path, json_dict, force_overwrite, sort_keys):
        # Try to dump the temporary dictionary
        # If the file exists check for overwriting
        if os.path.exists(json_path):
            # If file is not forcibly overwritten
            if not force_overwrite:
                print("[WARN] Target '" + json_path + "' already exists,")
                overwrite = input("       Overwrite it? (y/n) ")
            # If file is forcibly overwritten
            else:
                overwrite = "y"
            # If overwriting the file
            if overwrite.lower() == "y" or overwrite.lower() == "yes":
                LocresExporter.__dump_json_parse(json_path, json_dict, "wt", sort_keys=sort_keys)
        # File does not exist
        else:
            LocresExporter.__dump_json_parse(json_path, json_dict, "xt", sort_keys=sort_keys)

    def __archive_json(self, json_dict):
        if os.path.exists(PACKAGE_ROOT + "\\" + LOCRES_CONFIG):
            json_paths = load_config(base_folder=PACKAGE_ROOT + "\\")
            json_path = self.apply_game_version_to_path(self.valorant_exe, json_paths["output_path"])
            write_type = "wt" if os.path.exists(json_path) else "xt"
            LocresExporter.__dump_json_parse(json_path, json_dict, write_type)

    @staticmethod
    def __dump_json_parse(json_path, json_dict, write_type, sort_keys=False):
        # Dump the temporary dictionary
        with open(json_path, write_type) as json_locres:
            json.dump(json_dict, json_locres, indent=4, sort_keys=sort_keys)


def load_config(base_folder=""):
    # Load locres_config.json
    # If config exists
    if os.path.exists(base_folder + LOCRES_CONFIG):
        # Try to load JSON
        try:
            with open(base_folder + LOCRES_CONFIG, "rt") as config_file:
                return json.load(config_file)
        # If the JSON cannot be parsed
        except ValueError:
            print("[ERROR] '" + LOCRES_CONFIG + "' has an invalid structure\n")
            exit()
        except OSError:
            print("[ERROR] Could not open '" + LOCRES_CONFIG + "'\n")
            exit()
    # If config does not exist
    else:
        # Create template dictionary
        config_dict = {"quickbms_path": "", "ut4_path": "", "ul_path": "",
                       "valorant_path": "", "working_path": "", "output_path": ""}
        # Dump template config JSON
        with open(base_folder + LOCRES_CONFIG, "xt") as paths_file:
            json.dump(config_dict, paths_file, indent=4)
            print("[ERROR] Created '" + LOCRES_CONFIG + "', fill out before running again\n")
            exit()


if __name__ == "__main__":
    # Base structure for exporting the JSON
    exporter = LocresExporter(VALORANT_PATH +
                              os.path.normpath("live\\ShooterGame\\Binaries\\Win64\\VALORANT-Win64-Shipping.exe"),
                              "en_US", "en-US")
    print("[QuickBMS] Exporting Locres")
    locres_pak = VALORANT_PATH + RELATIVE_LOCRES_PAK
    exporter.export_locres(locres_pak)
    print("[UnrealLocres] Converting Locres to CSV")
    exporter.locres_to_csv()
    print("Converting CSV to JSON")
    exporter.csv_to_json(exporter.config["output_path"], force_overwrite=True)
    print("Done")
