// Two shared synchronous ROM banks. Both paths are read for each lane.
// ce accepts one address pair; data and immutable tag qualify one clock later.
// rst_n resets only response ownership, not inferred ROM contents/data registers.
module m2_polyphony_rom #(
    parameter integer TAG_BITS=77,
    parameter PIANO_FILE="rom/piano_band_4x256_8191.mem",
    parameter TRIANGLE_FILE="rom/triangle_wavetable.hex"
) (
    input wire clk,rst_n,ce,
    input wire [9:0] piano_addr,triangle_addr,
    input wire [TAG_BITS-1:0] tag_in,
    output logic valid,
    output logic [TAG_BITS-1:0] tag_out,
    output logic signed [15:0] piano_data,triangle_data
);
    logic signed [15:0] piano [0:1023],triangle [0:1023];
    initial begin
        $readmemh(PIANO_FILE,piano);
        $readmemh(TRIANGLE_FILE,triangle);
    end
    always_ff @(posedge clk) if(ce) begin
        piano_data<=piano[piano_addr];
        triangle_data<=triangle[triangle_addr];
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin valid<=0;tag_out<=0;end
        else begin valid<=ce;if(ce)tag_out<=tag_in;end
    end
    // synthesis translate_off
    initial begin
        for(integer a=0;a<1024;a++) begin
            if(^piano[a]===1'bx) $fatal(1,"POLY_ROM_PIANO_MISSING");
            if(^triangle[a]===1'bx) $fatal(1,"POLY_ROM_TRIANGLE_MISSING");
        end
    end
    // synthesis translate_on
endmodule
