import argparse
from helpers.sim_types import Config, ParserArgs, DeviceEntry
from helpers.helpers import load_config
from helpers.main_send import MainSend

def main() -> None:
    config: Config = load_config()

    def device_lookup(name: str) -> list[DeviceEntry]:
        for device in config.devices:
            if device.device_name == name:
                return [device]
        raise argparse.ArgumentTypeError(
            f"Unknown device '{name}', Avalible Choices: {[d.device_name for d in config.devices]}"
        )

    parser = argparse.ArgumentParser(
        prog="Data Sending Simulator",
        usage="How to",
        description="What the program does",
        epilog="Text at the bottom to help"
    )
    parser.add_argument(
        "-f",
        "--files",
        help="Specify custom data files",
        type=str,
        nargs="+",
        default = config.default_data_file
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
        help=f"List of avalible devices",
        type=device_lookup,
        default=[config.devices[0]]
    )

    raw = parser.parse_args()
    args = ParserArgs.model_validate(vars(raw))
    MainSend.run_sim(args)


if __name__ == "__main__":
    main()