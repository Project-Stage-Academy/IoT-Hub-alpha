import argparse
import json
from assets.pydantic_types import Config, PayloadEnvelope
from assets.main import MainSim


def main() -> None:
    with open("config.simulator.json", "r") as f:
        raw = json.load(f)
    config = Config.model_validate(raw)

    def device_lookup(name: str) -> PayloadEnvelope:
        for device in config.devices:
            if device.name == name:
                return device
        raise argparse.ArgumentTypeError(
            f"Unknown device '{name}', Avalible Choices: {[d.name for d in config.devices]}"
        )

    parser = argparse.ArgumentParser(
        prog="Data Sending Simulator",
        usage="How to",
        description=(f"Send test telemetry data to HTTP/MQTT endpoint \n"
                     f"supports infinite data stream, checks responses and compares them to set values, can preform loadtesting"),
        epilog="For further info consult docs/simulator.md"
    )
    parser.add_argument(
        "-f",
        "--files",
        help="Specify custom data file/s",
        type=str,
        nargs="+",
        choices = config.default_data_file,
        default = [file for file in config.default_data_file]
    )
    parser.add_argument(
        "-m",
        "--mode",
        help="Data send protocol, HTTTP or MQTT",
        type=str,
        choices=['http', 'mqtt'],
        default="http",
    )
    parser.add_argument(
        "-u",
        "--url",
        help="URL of the recieving server",
        type=str,
        default=config.default_url,
    )
    parser.add_argument(
        "-c",
        "--count",
        help="Amount of requests, 0 for infinite untill manually cancelled",
        type=int,
        default=10,
    )
    parser.add_argument(
        "-r",
        "--rate",
        help="Rate of sent requests measured in seconds",
        type=int,
        default=10,
    )
    parser.add_argument(
        "-d",
        "--devices",
        help=f"List of avalible devices: {", ".join(d.name for d in config.devices)}",
        type=device_lookup,
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "-l",
        "--log",
        help="Outputs results in sim_log.txt",
        action="store_true",
    )

    raw = parser.parse_args()
    MainSim.create_tasks(raw)

    

if __name__ == "__main__":
    main()