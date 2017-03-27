from ansible.module_utils.facts import GenericBsdIfconfigNetwork


class DarwinNetwork(GenericBsdIfconfigNetwork):
    """
    This is the Mac OS X/Darwin Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged
    """
    platform = 'Darwin'

    # media line is different to the default FreeBSD one
    def parse_media_line(self, words, current_if, ips):
        # not sure if this is useful - we also drop information
        current_if['media'] = 'Unknown'  # Mac does not give us this
        current_if['media_select'] = words[1]
        if len(words) > 2:
            # MacOSX sets the media to '<unknown type>' for bridge interface
            # and parsing splits this into two words; this if/else helps
            if words[1] == '<unknown' and words[2] == 'type>':
                current_if['media_select'] = 'Unknown'
                current_if['media_type'] = 'unknown type'
            else:
                current_if['media_type'] = words[2][1:-1]
        if len(words) > 3:
            current_if['media_options'] = self.get_options(words[3])
