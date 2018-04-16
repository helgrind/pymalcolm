from malcolm.yamlutil import make_block_creator, check_yaml_names

mqtt_server_block = make_block_creator(__file__, "mqtt_server_block.yaml")

__all__ = check_yaml_names(globals())
