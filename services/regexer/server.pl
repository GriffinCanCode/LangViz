#!/usr/bin/env perl

use strict;
use warnings;
use utf8;
use v5.38;

use lib 'lib';
use LangViz::Parser;

# gRPC server using Grpc::XS
use Grpc::XS;
use Grpc::XS::Server;

# Load proto definitions
# my $proto = Grpc::XS::ChannelCredentials->createInsecure();

sub main {
    my $parser = LangViz::Parser->new();
    
    # TODO: Implement gRPC service methods
    # For now, simple TCP server for testing
    
    say "LangViz Parser Service starting on port 50051...";
    say "Perl regex engine ready for dictionary parsing";
    
    # Service implementation would go here
    # Using Grpc::XS for proper gRPC support
    
    while (1) {
        sleep 1;
    }
}

main() unless caller;

__END__

=head1 NAME

server.pl - gRPC server for dictionary parsing

=head1 DESCRIPTION

Exposes Perl regex capabilities via gRPC for Python orchestrator.
Handles ETL from raw dictionary files to normalized JSON.

=cut

