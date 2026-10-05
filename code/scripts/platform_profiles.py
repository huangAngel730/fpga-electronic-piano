"""Explicit platform identities; catalog entries do not authorize board release."""
import argparse
import copy
import json

BASE_CLOCKS = {
    'sys_clk': ('Base', 20.0, 50.0, '', 'sys_clk'),
    'video_pixel': ('Generated', 40.0, 25.0, 'sys_clk', 'u_visual/u_video_pll/PLLA_inst/CLKOUT1'),
    'video_serial': ('Generated', 8.0, 125.0, 'sys_clk', 'u_visual/u_video_pll/PLLA_inst/CLKOUT0')}
CLOCKS40 = {
    'ref_clk': ('Base', 20.0, 50.0, '', 'sys_clk'),
    'sys_clk': ('Generated', 25.0, 40.0, 'ref_clk', 'u_visual/u_video_pll/PLLA_inst/CLKOUT2'),
    'video_pixel': ('Generated', 40.0, 25.0, 'ref_clk', 'u_visual/u_video_pll/PLLA_inst/CLKOUT1'),
    'video_serial': ('Generated', 8.0, 125.0, 'ref_clk', 'u_visual/u_video_pll/PLLA_inst/CLKOUT0')}
BALLS = {'sys_clk':'V22', 'sys_rst_n':'AA13', 'key_n[0]':'AB13', 'key_n[1]':'Y12',
         'midi_rx':'R17', 'uart_tx':'U15', 'i2s_bclk':'Y17', 'i2s_lrck':'AB17',
         'i2s_din':'AA16', 'pa_en':'AB16', 'tmds_clk_p':'G15,G16',
         'tmds_data_p[0]':'J14,H14', 'tmds_data_p[1]':'J15,H15', 'tmds_data_p[2]':'K17,J17'}
BANK60 = {'sys_clk':7, 'sys_rst_n':9, 'key_n[0]':9, 'key_n[1]':9, 'midi_rx':6,
          'uart_tx':6, 'i2s_bclk':7, 'i2s_lrck':7, 'i2s_din':7, 'pa_en':7,
          'tmds_clk_p':4, 'tmds_data_p[0]':4, 'tmds_data_p[1]':4, 'tmds_data_p[2]':5}
BANK138 = {'sys_clk':4, 'sys_rst_n':5, 'key_n[0]':5, 'key_n[1]':5, 'midi_rx':4,
           'uart_tx':5, 'i2s_bclk':5, 'i2s_lrck':5, 'i2s_din':5, 'pa_en':5,
           'tmds_clk_p':3, 'tmds_data_p[0]':3, 'tmds_data_p[1]':3, 'tmds_data_p[2]':3}

# Human decision: future expansion uses actual core40, while 60K50 remains
# the unchanged demo/fallback. This is a plan, NOT approval of a candidate.fs.
PREFERRED_EXPANSION_SYS_HZ = 40_000_000
PROFILE_POLICY = {
    'decision_date':'2026-10-05',
    'future_expansion_sys_hz':PREFERRED_EXPANSION_SYS_HZ,
    'audio_sample_hz':48_000, 'pixel_hz':25_000_000, 'serial_hz':125_000_000,
    '60k_demo_retained':True, 'selected_hold_profile_not_frozen':True,
    'I_L_evidence_pending':True, 'board_release_allowed':False}


def pins(is138):
    result = {}
    banks = BANK138 if is138 else BANK60
    for name, ball in BALLS.items():
        low = not is138 and name in ('sys_rst_n', 'key_n[0]', 'key_n[1]')
        pair = name.replace('_p', '_n') if name.startswith('tmds_') else '-'
        result[name] = {'Loc./Bank':ball+'/'+str(banks[name]), 'Constraint':'Y',
                        'Dir.':'in' if name in ('sys_clk','sys_rst_n','key_n[0]','key_n[1]','midi_rx') else 'out',
                        'Diff Pair':pair, 'IO Type':'LVDS25' if pair!='-' else ('LVCMOS15' if low else 'LVCMOS33'),
                        'BankVccio':'1.5' if low else '3.3',
                        'Drive':'OFF' if name in ('sys_clk','sys_rst_n','key_n[0]','key_n[1]','midi_rx') else ('3.5' if pair!='-' else '8'),
                        'Pull Mode':'UP' if name in ('sys_rst_n','key_n[0]','key_n[1]','midi_rx','uart_tx') else 'NONE'}
    return result


def profile(name):
    allowed = ('60k_b50', '138k_c50', '138k_c40_hold055', '138k_c40_hold065')
    if name not in allowed:
        raise ValueError('Unknown/unapproved profile: '+name)
    is138 = name.startswith('138')
    is40 = '_c40_' in name
    hold = .650 if name.endswith('065') else .550
    data = {'name':name, 'part':'GW5AST-LV138PG484AC1/I0' if is138 else 'GW5AT-LV60PG484AC1/I0',
            'version':'C' if is138 else 'B', 'device_id':'gw5ast138c-007' if is138 else 'gw5at60b-002',
            'sys_hz':40_000_000 if is40 else 50_000_000,
            'clocks':copy.deepcopy(CLOCKS40 if is40 else BASE_CLOCKS), 'pins':pins(is138),
            'hold_uncertainty_ns':hold, 'setup_uncertainty_ns':1.0,
            'reset_locs':['R44C168[1][A]','R44C168[1][B]'] if is138 else ['R49C101[1][A]','R49C101[1][B]'],
            'place_option':0, 'route_option':2 if is40 else (1 if is138 else 0),
            'DSP':46, 'BSRAM':20, 'vccx':'1.8' if is138 else '3.3',
            'source_set':'V0171 frozen four-voice audio and strict visual, no new panel/T027/effect',
            'hardware_release_allowed':False}
    if name.endswith('065'):
        data['additional_ff_locations'] = {
            'g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0':'R83C99[1][B]',
            'g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0':'R87C101[0][A]'}
        data['status'] = 'handoff profile only: original I/L input/report package not yet received'
    else:
        data['additional_ff_locations'] = {}
    hz = data['sys_hz']
    data['parameters'] = {
        'sample_hz':48_000, 'frame_floor_cycles':hz//48_000, 'frame_ceil_cycles':(hz+47_999)//48_000,
        'midi_baud':31_250, 'midi_divisor':hz//31_250, 'continuous_control_cycles':(hz+999)//1000,
        'debounce_cycles':hz//1000*3, 'stat_baud_target':115_200, 'stat_divisor':hz//115_200,
        'stat_actual_baud':hz/(hz//115_200), 'stat_period_cycles':hz//4,
        'BCLK_target':3_072_000, 'BCLK_NCO_step':((6_144_000<<32)+hz//2)//hz,
        'diagnostic_mode_cycles':hz*5, 'diagnostic_frame_cycles':hz*420//25_000}
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile')
    args = parser.parse_args()
    print(json.dumps(profile(args.profile), indent=2))
