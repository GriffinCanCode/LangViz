#!/usr/bin/env perl

use strict;
use warnings;
use utf8;
use v5.38;
use feature 'signatures';
no warnings 'experimental::signatures';

use lib 'lib';
use LangViz::Parser;

use JSON::PP;
use IO::Socket::INET;
use Data::Dumper;

=head1 NAME

server.pl - High-performance dictionary parsing service

=head1 DESCRIPTION

Exposes Perl's superior regex engine via simple JSON-RPC over TCP.
Handles messy, inconsistent linguistic data that Python regex struggles with.

Architecture choice: Using JSON over TCP instead of gRPC for simplicity.
Perl's Grpc::XS is less mature than Python's gRPC implementation.

=cut

my $PORT = $ENV{PARSER_PORT} // 50051;
my $HOST = $ENV{PARSER_HOST} // '0.0.0.0';

sub main {
    my $parser = LangViz::Parser->new();
    
    say "╔════════════════════════════════════════════════════════╗";
    say "║  LangViz Perl Parser Service                          ║";
    say "║  Perl $^V regex engine for messy dictionary data      ║";
    say "╚════════════════════════════════════════════════════════╝";
    say "";
    say "Listening on $HOST:$PORT...";
    say "Protocol: JSON-RPC over TCP";
    say "Ready to parse linguistic data with Perl regex power!";
    say "";
    
    # Create TCP server
    my $server = IO::Socket::INET->new(
        LocalHost => $HOST,
        LocalPort => $PORT,
        Proto     => 'tcp',
        Listen    => 5,
        ReuseAddr => 1,
    ) or die "Cannot create socket: $!";
    
    # Accept client connections
    while (my $client = $server->accept()) {
        $client->autoflush(1);
        
        eval {
            handle_client($client, $parser);
        };
        
        if ($@) {
            warn "Error handling client: $@";
        }
        
        close $client;
    }
}

sub handle_client($client, $parser) {
    # Read JSON-RPC request
    my $request_line = <$client>;
    return unless $request_line;
    
    chomp $request_line;
    
    my $request = decode_json($request_line);
    my $method = $request->{method};
    my $params = $request->{params} // {};
    my $id = $request->{id};
    
    say "[Request] $method " . ($params->{filepath} // $params->{text} // '');
    
    my $response;
    
    eval {
        if ($method eq 'parse_starling') {
            $response = parse_starling_handler($parser, $params);
        }
        elsif ($method eq 'normalize_text') {
            $response = normalize_text_handler($parser, $params);
        }
        elsif ($method eq 'extract_ipa') {
            $response = extract_ipa_handler($parser, $params);
        }
        elsif ($method eq 'validate_ipa') {
            $response = validate_ipa_handler($parser, $params);
        }
        else {
            die "Unknown method: $method";
        }
    };
    
    if ($@) {
        # Error response
        my $error_response = {
            jsonrpc => '2.0',
            error => {
                code => -32603,
                message => "$@",
            },
            id => $id,
        };
        print $client encode_json($error_response) . "\n";
        return;
    }
    
    # Success response
    my $success_response = {
        jsonrpc => '2.0',
        result => $response,
        id => $id,
    };
    
    print $client encode_json($success_response) . "\n";
}

sub parse_starling_handler($parser, $params) {
    my $filepath = $params->{filepath} or die "Missing filepath parameter";
    
    my $entries = $parser->parse_starling_dict($filepath);
    
    return {
        entries => $entries,
        total_parsed => scalar @$entries,
        warnings => [],
    };
}

sub normalize_text_handler($parser, $params) {
    my $text = $params->{text} or die "Missing text parameter";
    my $operations = $params->{operations} // ['nfc', 'lowercase'];
    
    my $normalized = $parser->normalize_text($text, $operations);
    
    return {
        normalized => $normalized,
    };
}

sub extract_ipa_handler($parser, $params) {
    my $text = $params->{text} or die "Missing text parameter";
    my $notation = $params->{notation} // 'kirshenbaum';
    
    my $ipa = '';
    my $success = 0;
    
    if ($notation eq 'kirshenbaum') {
        $ipa = $parser->extract_ipa_from_kirshenbaum($text);
        $success = 1;
    }
    else {
        die "Unknown notation: $notation";
    }
    
    return {
        ipa => $ipa,
        success => $success ? JSON::PP::true : JSON::PP::false,
    };
}

sub validate_ipa_handler($parser, $params) {
    my $ipa = $params->{ipa} or die "Missing ipa parameter";
    
    my $is_valid = $parser->validate_ipa($ipa);
    
    return {
        valid => $is_valid ? JSON::PP::true : JSON::PP::false,
    };
}

# Handle graceful shutdown
$SIG{INT} = $SIG{TERM} = sub {
    say "\nShutting down gracefully...";
    exit 0;
};

main() unless caller;

__END__

=head1 PROTOCOL

JSON-RPC 2.0 over TCP. Each request/response is a single JSON line.

=head2 Methods

=head3 parse_starling

Parse Starling format dictionary file.

Request:
    {
        "jsonrpc": "2.0",
        "method": "parse_starling",
        "params": {"filepath": "/path/to/file.txt"},
        "id": 1
    }

Response:
    {
        "jsonrpc": "2.0",
        "result": {
            "entries": [...],
            "total_parsed": 123,
            "warnings": []
        },
        "id": 1
    }

=head3 normalize_text

Normalize text using Perl regex.

Request:
    {
        "jsonrpc": "2.0",
        "method": "normalize_text",
        "params": {
            "text": "Some Text",
            "operations": ["nfc", "lowercase"]
        },
        "id": 2
    }

Response:
    {
        "jsonrpc": "2.0",
        "result": {"normalized": "some text"},
        "id": 2
    }

=head3 extract_ipa

Convert notation systems to IPA.

Request:
    {
        "jsonrpc": "2.0",
        "method": "extract_ipa",
        "params": {
            "text": "wodr",
            "notation": "kirshenbaum"
        },
        "id": 3
    }

Response:
    {
        "jsonrpc": "2.0",
        "result": {
            "ipa": "wódr̥",
            "success": true
        },
        "id": 3
    }

=cut

