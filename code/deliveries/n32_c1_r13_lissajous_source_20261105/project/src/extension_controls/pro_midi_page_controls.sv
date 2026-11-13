// Raw MIDI observer only: no event output, ready, or audio feedback.
// rst_n is active-low SYNCHRONOUS reset, matching midi_event_parser.
// UART error clears framing context only; the selected page survives errors,
// SysEx and system-common. Last complete valid CC71/CC74 chooses the page.
`timescale 1ns/1ps
module pro_midi_page_controls (
    input wire clk,rst_n,
    input wire [7:0] midi_byte,
    input wire midi_byte_valid,midi_byte_error,
    output logic [2:0] page_select
);
    logic [7:0] running_status;
    logic [6:0] first_data_byte;
    logic channel_data_pending;
    logic [1:0] system_data_remaining;
    logic sysex_active;
    function automatic logic one_data(input logic [3:0] status);
        one_data=(status==4'hC)||(status==4'hD);
    endfunction
    function automatic logic [1:0] system_bytes(input logic [7:0] status);
        case(status)
            8'hF1,8'hF3:system_bytes=1;
            8'hF2:system_bytes=2;
            default:system_bytes=0;
        endcase
    endfunction
    always_ff @(posedge clk)begin
        if(!rst_n)begin
            running_status<=0;first_data_byte<=0;channel_data_pending<=0;
            system_data_remaining<=0;sysex_active<=0;
            page_select<=0;
        end else if(midi_byte_valid)begin
            if(midi_byte_error)begin
                running_status<=0;first_data_byte<=0;channel_data_pending<=0;
                system_data_remaining<=0;sysex_active<=0;
            end else if(midi_byte>=8'hF8)begin
                // All real-time statuses, including FF, preserve context.
            end else if(sysex_active)begin
                if(midi_byte==8'hF7)sysex_active<=0;
                else if(midi_byte[7])begin
                    sysex_active<=(midi_byte==8'hF0);
                    running_status<=(midi_byte[7:4]<=4'hE)?midi_byte:8'd0;
                    channel_data_pending<=0;
                    system_data_remaining<=(midi_byte[7:4]==4'hF)?system_bytes(midi_byte):2'd0;
                end
            end else if(midi_byte[7])begin
                channel_data_pending<=0;first_data_byte<=0;
                if(midi_byte[7:4]<=4'hE)begin
                    running_status<=midi_byte;system_data_remaining<=0;
                end else begin
                    running_status<=0;system_data_remaining<=system_bytes(midi_byte);
                    if(midi_byte==8'hF0)sysex_active<=1;
                end
            end else if(system_data_remaining!=0)begin
                system_data_remaining<=system_data_remaining-1'b1;
            end else if(running_status[7])begin
                if(one_data(running_status[7:4]))channel_data_pending<=0;
                else if(!channel_data_pending)begin
                    first_data_byte<=midi_byte[6:0];channel_data_pending<=1;
                end else begin
                    channel_data_pending<=0;
                    // Complete, error-free two-data-byte channel message only.
                    if(running_status[7:4]==4'hB)begin
                        // K3/K4 are absolute controls, with no toggle state.
                        // Every completed value can reclaim its interval page.
                        if(first_data_byte==7'd71)
                            page_select<=(midi_byte[6:0]<=7'd60) ? 3'd0 : 3'd1;
                        else if(first_data_byte==7'd74)begin
                            if(midi_byte[6:0]<=7'd40)page_select<=3'd2;
                            else if(midi_byte[6:0]<=7'd80)page_select<=3'd3;
                            else page_select<=3'd4;
                        end
                    end
                end
            end
        end
    end
endmodule
