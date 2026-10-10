// Isolated synchronous eight-byte-lane RAM candidate; original T057 protocol.
// Read-only dependencies: original common/uart_rx.sv and uart_tx.sv.
// 40MHz synchronous active-low reset. No new clock, no audio/visual events.
// Double bank: failed staging writes never alter published storage.
`timescale 1ns/1ps
module score_transfer_bram_candidate #(
    parameter integer CLK_HZ = 40000000,
    parameter integer BAUD = 115200,
    parameter integer FRAME_TIMEOUT = 800000,
    parameter integer SESSION_TIMEOUT = 200000000
) (
    input logic clk, rst_n, uart_rx_i,
    output logic uart_tx_o,
    input logic rd_req,
    input logic [8:0] rd_index,
    output logic rd_valid,
    output logic [63:0] rd_event,
    output logic committed_valid,
    output logic [9:0] committed_count,
    output logic [31:0] committed_score_id,
    output logic commit_pulse,
    output logic [7:0] last_error
);
    function automatic [15:0] crc_byte(input [15:0] old_crc, input [7:0] value);
        reg [15:0] c;
        integer bit_n;
        begin
            c = old_crc ^ {value, 8'b0};
            for (bit_n=0; bit_n<8; bit_n=bit_n+1)
                c = c[15] ? ((c << 1) ^ 16'h1021) : (c << 1);
            crc_byte = c;
        end
    endfunction

    logic [7:0] rx_data, tx_data;
    logic rx_valid, rx_error, rx_busy, tx_valid, tx_ready;
    uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) receiver(
        .clk(clk), .rst_n(rst_n), .rx(uart_rx_i), .rx_data(rx_data),
        .rx_valid(rx_valid), .frame_err(rx_error), .rx_busy(rx_busy));
    uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) transmitter(
        .clk(clk), .rst_n(rst_n), .tx_data(tx_data), .tx_valid(tx_valid),
        .tx_ready(tx_ready), .tx(uart_tx_o));

    // Protocol parser states, and bounded byte-at-a-time commit verification.
    localparam SEEK=0, MAGIC2=1, BODY=2, CRC_LO=3, CRC_HI=4, EXEC=5,
               COPY=6, VERIFY=7, RESP=8, DRAIN=9, ERROR_WAIT=10,
               VERIFY_USE=11, READ_WAIT=12, READ_REPLY=13,
               REPLY_CRC_FETCH=14, REPLY_CRC_STEP=15, REPLY_CRC_FINISH=16,
               COPY_FETCH=17;
    logic [4:0] state;
    // Assertion remains immediate at the same sampled reset edge. Release is
    // fenced for one extra core clock so RAM history/control cannot act before
    // the reset sample is established. UART primitives retain their original
    // reset. This real startup fence also removes the direct external-reset
    // shortcut to the core's synchronous SET/RESET network.
    logic reset_ready;
    always_ff @(posedge clk) reset_ready <= rst_n;
    wire core_rst_n = rst_n && reset_ready;
    // Only the BEGIN header/metadata needs random parallel field access.
    // Full request/history bytes live in synchronous ping-pong BSRAM below.
    logic [7:0] body[0:23];
    logic request_bank, cached_bank, body_compare_pending;
    logic [7:0] body_compare_byte, copy_byte, cached_body_byte;
    logic [7:0] reply[0:33], last_reply[0:33];
    logic [63:0] ram_public, ram_internal;
    logic read_seen;
    logic active, published_bank, stage_bank, cache_valid, same_body;
    logic [15:0] session_id, next_seq, received, total_bytes, expected_crc;
    logic [9:0] event_count;
    logic [31:0] score_id;
    logic [15:0] request_session, request_seq, request_offset, payload_len;
    logic [7:0] command, version;
    logic [15:0] frame_crc, wire_crc, score_crc;
    logic [7:0] pos, body_length, cached_length, copy_pos;
    logic [5:0] reply_length, reply_pos, cached_reply_length;
    logic [31:0] frame_timer, session_timer, previous_tick;
    logic [12:0] verify_pos;
    logic [63:0] event_shift;
    logic cache_this;
    logic [7:0] pending_error;
    logic [15:0] reply_crc;
    logic [7:0] reply_crc_byte;
    logic [5:0] reply_crc_pos;
    logic reply_has_event;
    wire request_write = core_rst_n && state==BODY && rx_valid && !rx_error &&
                         !(active && session_timer>=SESSION_TIMEOUT-1) &&
                         !(frame_timer>=FRAME_TIMEOUT-1);
    wire [7:0] copy_byte_index = 8'd10 + copy_pos;
    score_request_cache request_history(
        .clk(clk), .write_enable(request_write),
        .current_address({request_bank, request_write ? pos : copy_byte_index}),
        .cached_address({cached_bank,pos}), .write_data(rx_data),
        .current_data(copy_byte), .cached_data(cached_body_byte));
    wire public_enable = rst_n && rd_req && committed_valid && rd_index < committed_count;
    wire [12:0] copy_address = {1'b0,received[11:0]} + copy_pos;
    wire [9:0] port_b_address = (state==EXEC && command==6) ||
                               state==READ_WAIT || state==READ_REPLY
        ? {published_bank,request_offset[8:0]}
        : state==COPY ? {stage_bank,copy_address[11:3]}
        : {stage_bank,verify_pos[11:3]};
    // Match parser priority: no last staging write may escape timeout/reset.
    wire port_b_write = core_rst_n && state==COPY && command==2 && copy_pos<payload_len &&
                        !(active && session_timer>=SESSION_TIMEOUT-1) &&
                        !(rx_valid && rx_error);
    genvar lane;
    generate for (lane=0; lane<8; lane=lane+1) begin: byte_lanes
        score_byte_lane storage(
            .clk(clk), .a_enable(public_enable),
            .a_address({published_bank,rd_index}),
            .a_data(ram_public[lane*8 +: 8]),
            .b_address(port_b_address),
            .b_write(port_b_write && copy_address[2:0]==lane),
            .b_data(copy_byte),
            .b_read(ram_internal[lane*8 +: 8]));
    end endgenerate
    wire [7:0] verify_byte = ram_internal[verify_pos[2:0]*8 +: 8];
    wire [63:0] event_next = {verify_byte,event_shift[63:8]};
    wire event_bad = event_next[39:32] > 1 || event_next[47:40] > 15 ||
        event_next[55:48] > 127 || event_next[63:56] > 127 ||
        (event_next[39:32] == 0 && event_next[63:56] == 0) ||
        (verify_pos >= 8 && event_next[31:0] < previous_tick);

    // RAM port A owns every public request, independently of UART port B.
    // At COMMIT's edge the old published_bank is sampled (NBA semantics).
    // Contents are never reset; read_seen masks the uninitialized output only.
    assign rd_event = read_seen ? ram_public : 64'b0;
    always_ff @(posedge clk) begin
        rd_valid <= public_enable;
        if (!rst_n) read_seen <= 0;
        else if (public_enable) read_seen <= 1;
    end

    // Response is assembled once; TX must hold data/valid through uart_tx handshake.
    assign tx_valid = state == RESP && reply_pos < reply_length;
    assign tx_data = reply[reply_pos];

    task automatic respond(input [7:0] error_code, input logic with_event);
        reg [7:0] buffer[0:33];
        integer n, end_body;
        begin
            // Snapshot metadata/event bytes once. CRC is subsequently folded
            // one byte per two clocks; no 22/30-byte combinational CRC chain.
            for (n=0; n<34; n=n+1) buffer[n]=0;
            buffer[0]=8'ha5; buffer[1]=8'h5a; buffer[2]=1;
            buffer[3]=(error_code==0) ? 8'h80 : 8'h81;
            buffer[4]=request_session[7:0]; buffer[5]=request_session[15:8];
            buffer[6]=request_seq[7:0]; buffer[7]=request_seq[15:8];
            buffer[8]=request_offset[7:0]; buffer[9]=request_offset[15:8];
            buffer[10]=with_event ? 20 : 12; buffer[11]=0;
            buffer[12]=command; buffer[13]=error_code;
            buffer[14]={7'b0,committed_valid}; buffer[15]={7'b0,active};
            buffer[16]=committed_count[7:0]; buffer[17]={6'b0,committed_count[9:8]};
            buffer[18]=committed_score_id[7:0]; buffer[19]=committed_score_id[15:8];
            buffer[20]=committed_score_id[23:16]; buffer[21]=committed_score_id[31:24];
            buffer[22]=received[7:0]; buffer[23]=received[15:8];
            if (with_event)
                for (n=0; n<8; n=n+1)
                    buffer[24+n]=ram_internal[n*8 +: 8];
            end_body=with_event ? 32 : 24;
            for (n=0; n<34; n=n+1) reply[n]<=buffer[n];
            reply_length <= end_body+2;
            reply_pos <= 0;
`ifdef MUTANT_RESPONSE_CRC
            reply_crc <= 16'hfffe;
`else
            reply_crc <= 16'hffff;
`endif
            reply_crc_pos <= 2;
            reply_has_event <= with_event;
            last_error <= error_code;
            cache_this <= error_code==0;
            state <= REPLY_CRC_FETCH;
        end
    endtask

    integer j;
    always_ff @(posedge clk) begin
        if (!core_rst_n) begin
            state<=SEEK; active<=0; published_bank<=0; stage_bank<=1;
            committed_valid<=0; committed_count<=0; committed_score_id<=0;
            commit_pulse<=0; last_error<=0; frame_timer<=0; session_timer<=0;
            cache_valid<=0; same_body<=0; cached_length<=0; cached_reply_length<=0;
            request_bank<=0; cached_bank<=1;
            body_compare_pending<=0; body_compare_byte<=0;
            pos<=0; body_length<=0; payload_len<=0; command<=0; version<=0;
            request_session<=0; request_seq<=0; request_offset<=0;
            frame_crc<=16'hffff; wire_crc<=0; received<=0; total_bytes<=0;
            expected_crc<=0; score_crc<=16'hffff; session_id<=0; next_seq<=1;
            event_count<=0; score_id<=0; reply_pos<=0; reply_length<=0;
            copy_pos<=0; verify_pos<=0; event_shift<=0; previous_tick<=0; cache_this<=0; pending_error<=0;
            reply_crc<=16'hffff; reply_crc_byte<=0; reply_crc_pos<=0; reply_has_event<=0;
        end else begin
            commit_pulse<=0;
            // RAM B samples pos together with rx_data; consume its registered
            // result one clock later. Never compare an asynchronous wide mux.
            body_compare_pending<=request_write;
            if (request_write) body_compare_byte<=rx_data;
            if (body_compare_pending)
                same_body<=same_body && body_compare_byte==cached_body_byte;
            if (active) session_timer<=session_timer+1;
            else session_timer<=0;
            if (state==MAGIC2 || state==BODY || state==CRC_LO || state==CRC_HI || state==DRAIN)
                frame_timer<=frame_timer+1;
            else frame_timer<=0;

            if (state==RESP) begin
                if (tx_valid && tx_ready) begin
                    if (reply_pos==reply_length-1) begin
                        state<=SEEK;
                        if (cache_this) begin
                            // O(1) publication of byte history, not 1104 FFs
                            // copied on one high-fanout response-end enable.
                            cached_bank<=request_bank;
                            request_bank<=!request_bank;
                            for (j=0; j<34; j=j+1) last_reply[j]<=reply[j];
                            cached_length<=body_length;
                            cached_reply_length<=reply_length;
                            cache_valid<=1;
                        end
                    end else reply_pos<=reply_pos+1;
                end
            // Like the old RESP phase, a snapshotted reply is not preempted by
            // RX errors or session timeout. Reset still has absolute priority.
            // Separate register cuts isolate the byte mux from the CRC XORs.
            end else if (state==REPLY_CRC_FETCH) begin
                reply_crc_byte<=reply[reply_crc_pos];
                state<=REPLY_CRC_STEP;
            end else if (state==REPLY_CRC_STEP) begin
                reply_crc<=crc_byte(reply_crc,reply_crc_byte);
                if (reply_crc_pos==(reply_has_event ? 31 : 23)) state<=REPLY_CRC_FINISH;
                else begin reply_crc_pos<=reply_crc_pos+1; state<=REPLY_CRC_FETCH; end
            end else if (state==REPLY_CRC_FINISH) begin
                if (reply_has_event) begin
                    reply[32]<=reply_crc[7:0]; reply[33]<=reply_crc[15:8];
                end else begin
                    reply[24]<=reply_crc[7:0]; reply[25]<=reply_crc[15:8];
                end
                state<=RESP;
            end else if (active && session_timer>=SESSION_TIMEOUT-1) begin
                active<=0; cache_valid<=0; pending_error<=12; state<=ERROR_WAIT;
            end else if ((state==MAGIC2 || state==BODY || state==CRC_LO || state==CRC_HI || state==DRAIN)
                         && frame_timer>=FRAME_TIMEOUT-1) begin
                if (state==DRAIN) state<=SEEK;
                else begin cache_valid<=0; respond(12,0); end
            end else if (rx_valid && rx_error) begin
                cache_valid<=0; respond(14,0);
            end else case (state)
                SEEK: if (rx_valid && rx_data==8'ha5) state<=MAGIC2;
                MAGIC2: if (rx_valid) begin
                    frame_timer<=0;
                    if (rx_data==8'h5a) begin
                        state<=BODY; pos<=0; frame_crc<=16'hffff;
                        same_body<=cache_valid; payload_len<=0;
                    end else if (rx_data!=8'ha5) state<=SEEK;
                end
                BODY: if (rx_valid) begin
                    frame_timer<=0;
                    if (pos<24) body[pos]<=rx_data;
                    frame_crc<=crc_byte(frame_crc,rx_data);
                    case (pos)
                        0: version<=rx_data;
                        1: command<=rx_data;
                        2: request_session[7:0]<=rx_data;
                        3: request_session[15:8]<=rx_data;
                        4: request_seq[7:0]<=rx_data;
                        5: request_seq[15:8]<=rx_data;
                        6: request_offset[7:0]<=rx_data;
                        7: request_offset[15:8]<=rx_data;
                        8: payload_len[7:0]<=rx_data;
                        9: payload_len[15:8]<=rx_data;
                    endcase
                    if (pos==9) begin
                        if ({rx_data,payload_len[7:0]}>128) begin
                            respond(4,0); cache_this<=0;
                            // Enter drain only after sending NACK (flag in payload_len).
                            payload_len<=16'hffff;
                        end else begin
                            body_length<=10+payload_len[7:0];
                            if (payload_len[7:0]==0) state<=CRC_LO;
                        end
                    end else if (pos>=10 && pos==body_length-1) state<=CRC_LO;
                    pos<=pos+1;
                end
                CRC_LO: if (rx_valid) begin wire_crc[7:0]<=rx_data; state<=CRC_HI; frame_timer<=0; end
                CRC_HI: if (rx_valid) begin wire_crc[15:8]<=rx_data; state<=EXEC; frame_timer<=0; end
                EXEC: begin
                    if (wire_crc!=frame_crc) respond(1,0);
                    else if (version!=1) respond(2,0);
                    else if (cache_valid && same_body && body_length==cached_length) begin
                        for (j=0; j<34; j=j+1) reply[j]<=last_reply[j];
                        reply_pos<=0; reply_length<=cached_reply_length;
                        state<=RESP; cache_this<=0; session_timer<=0; last_error<=0;
                    end else case (command)
                        1: begin
                            if (payload_len!=14 || request_offset!=0) respond(4,0);
                            else if (request_session==0) respond(5,0);
                            else if (request_seq!=0) respond(6,0);
                            else if ({body[15],body[14]}==0 || {body[15],body[14]}>512 ||
                                {body[17],body[16]}!=({body[15],body[14]}<<3) ||
                                {body[23],body[22],body[21],body[20]}!=48000) respond(11,0);
                            else begin
                                active<=1; session_id<=request_session; next_seq<=1;
                                received<=0; session_timer<=0; stage_bank<=!published_bank;
                                score_id<={body[13],body[12],body[11],body[10]};
                                event_count<={body[15],body[14]};
                                total_bytes<={body[17],body[16]}; expected_crc<={body[19],body[18]};
                                // Respond in COPY after metadata takes effect.
                                copy_pos<=0; state<=COPY;
                            end
                        end
                        2: begin
                            if (!active || request_session!=session_id) respond(5,0);
                            else if (request_seq!=next_seq) respond(6,0);
                            else if (request_offset!=received) respond(7,0);
                            else if (payload_len==0 || {1'b0,received}+{1'b0,payload_len}>total_bytes) respond(4,0);
                            else begin copy_pos<=0; state<=COPY_FETCH; session_timer<=0; end
                        end
                        3: begin
                            if (payload_len!=0 || request_offset!=0) respond(4,0);
                            else if (!active || request_session!=session_id) respond(5,0);
                            else if (request_seq!=next_seq) respond(6,0);
                            else if (received!=total_bytes) respond(8,0);
                            else begin
                                score_crc<=16'hffff; verify_pos<=0;
                                previous_tick<=0; event_shift<=0; state<=VERIFY; session_timer<=0;
                            end
                        end
                        4: begin
                            if (payload_len!=0 || request_offset!=0) respond(4,0);
                            else begin active<=0; received<=0; state<=COPY; copy_pos<=0; end
                        end
                        5: if (payload_len!=0 || request_offset!=0) respond(4,0); else respond(0,0);
                        6: begin
                            if (payload_len!=0) respond(4,0);
                            else if (!committed_valid || request_offset>=committed_count) respond(13,0);
                            else state<=READ_WAIT;
                        end
                        default: respond(3,0);
                    endcase
                end
                COPY_FETCH: state<=COPY;
                COPY: begin
                    if (command==2 && copy_pos<payload_len) begin
                        // Byte write is owned by the eight lane memories.
                        copy_pos<=copy_pos+1;
                        state<=COPY_FETCH;
                    end else begin
                        // Extra cycle ensures response includes final received count.
                        if (command==2 && copy_pos==payload_len) begin
                            received<=received+payload_len; next_seq<=next_seq+1;
                            copy_pos<=copy_pos+1;
                        end
                        else respond(0,0);
                    end
                end
                READ_WAIT: state<=READ_REPLY;
                READ_REPLY: respond(0,1);
                VERIFY: begin
                    if (verify_pos<total_bytes) state<=VERIFY_USE;
                    else begin
                        if (score_crc!=expected_crc) begin
                            active<=0; cache_valid<=0; pending_error<=9; state<=ERROR_WAIT;
                        end else begin
`ifdef MUTANT_BANK_SWITCH
                            published_bank<=!stage_bank;
`else
                            published_bank<=stage_bank;
`endif
                            committed_valid<=1;
                            committed_count<=event_count; committed_score_id<=score_id;
                            commit_pulse<=1; active<=0;
                            state<=COPY; copy_pos<=0;
                        end
                    end
                end
                VERIFY_USE: begin
                        score_crc<=crc_byte(score_crc,verify_byte);
                        event_shift<=event_next;
                        if (verify_pos[2:0]==7) begin
                            if (event_bad) begin
                                active<=0; cache_valid<=0; pending_error<=10; state<=ERROR_WAIT;
                            end
                            else previous_tick<=event_next[31:0];
                        end
                        verify_pos<=verify_pos+1;
                        // Do not overwrite event_bad's terminal rejection.
                        if (!(verify_pos[2:0]==7 && event_bad)) state<=VERIFY;
                end
                DRAIN: if (rx_valid) frame_timer<=0;
                ERROR_WAIT: respond(pending_error,0);
                default: state<=SEEK;
            endcase
            // After oversized header response, ignore stream until idle timeout.
            if (state==RESP && tx_valid && tx_ready && reply_pos==reply_length-1 && payload_len==16'hffff)
                state<=DRAIN;
        end
    end
endmodule
