from exceptions import ReporterException


class Reporter:
    __report_groups: {str: (str, [str])} = {}

    @classmethod
    def add_report_group(cls, group_name: str, display_name: str):
        if group_name not in cls.__report_groups:
            cls.__report_groups[group_name] = (display_name, [])

    @classmethod
    def append_report(cls, group_name: str, report: str):
        if group_name in cls.__report_groups:
            cls.__report_groups[group_name][1].append(report)
        else:
            raise ReporterException(f"Unknown group \"{group_name}\"")

    @classmethod
    def to_str(cls):
        result = "\n\n".join(cls.__group_to_str(group) for group in cls.__report_groups.values())
        return result

    @staticmethod
    def __group_to_str(group: (str, [str])) -> str:
        result = "{display_name}: \n\t{reports}".format(
            display_name=group[0],
            reports='\n\t'.join(('\n\t\t'.join(report.split('\n'))) for report in group[1]))
        return result
