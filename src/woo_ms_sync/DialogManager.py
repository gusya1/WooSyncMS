
class DialogManager:

    def __init__(self, main_message, command_list):
        self.command_list = command_list
        self.main_message = main_message

    def main_dialog(self):
        command = input(self.main_message)
        if command in ['help', '?']:
            self.print_help()
            return self.main_dialog()
        userdata = self.command_list.get(command)
        if userdata is None:
            print("Unknown command.")
            self.print_help()
            return self.main_dialog()
        else:
            return userdata[1]()

    def print_help(self):
        print("Usage:")
        print("[?] or [help] - this message")
        for command, userdata, in self.command_list.items():
            print("[{}] - {}".format(command, userdata[0]))
