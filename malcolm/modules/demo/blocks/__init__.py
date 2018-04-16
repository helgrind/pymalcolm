from malcolm.yamlutil import make_block_creator, check_yaml_names

counter_block = make_block_creator(__file__, "counter_block.yaml")
hello_block = make_block_creator(__file__, "hello_block.yaml")
ticker_block = make_block_creator(__file__, "ticker_block.yaml")
scan_block = make_block_creator(__file__, "scan_block.yaml")
gauge_block = make_block_creator(__file__, "gauge_block.yaml")
string_block = make_block_creator(__file__, "string_block.yaml")
numsub_block = make_block_creator(__file__, "numsub_block.yaml")

__all__ = check_yaml_names(globals())
