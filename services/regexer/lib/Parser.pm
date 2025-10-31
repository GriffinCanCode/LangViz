package LangViz::Parser;

use strict;
use warnings;
use utf8;
use v5.38;

use Lingua::IPA;
use Unicode::Normalize;
use Text::Unidecode;

=head1 NAME

LangViz::Parser - Dictionary parsing and text normalization

=head1 SYNOPSIS

    my $parser = LangViz::Parser->new();
    my $entries = $parser->parse_starling_dict($filepath);
    my $normalized = $parser->normalize_text($text);

=cut

sub new {
    my ($class) = @_;
    return bless {
        ipa_validator => Lingua::IPA->new(),
    }, $class;
}

sub parse_starling_dict {
    my ($self, $filepath) = @_;
    
    open my $fh, '<:utf8', $filepath 
        or die "Cannot open $filepath: $!";
    
    my @entries;
    my %current_entry;
    
    while (my $line = <$fh>) {
        chomp $line;
        
        # Match headword pattern: \lx word
        if ($line =~ /^\\lx\s+(.+)$/) {
            $current_entry{headword} = $1;
        }
        # Match IPA: \ph [ipa]
        elsif ($line =~ /^\\ph\s+\[(.+)\]$/) {
            $current_entry{ipa} = $1;
        }
        # Match definition: \de text
        elsif ($line =~ /^\\de\s+(.+)$/) {
            $current_entry{definition} = $1;
        }
        # Match etymology: \et text
        elsif ($line =~ /^\\et\s+(.+)$/) {
            $current_entry{etymology} = $1;
        }
        # Match POS: \ps noun, verb, etc
        elsif ($line =~ /^\\ps\s+(.+)$/) {
            $current_entry{pos_tag} = $1;
        }
        # Entry boundary
        elsif ($line =~ /^$/ && keys %current_entry) {
            push @entries, {%current_entry};
            %current_entry = ();
        }
    }
    
    # Handle last entry
    push @entries, {%current_entry} if keys %current_entry;
    
    close $fh;
    return \@entries;
}

sub normalize_text {
    my ($self, $text, $operations) = @_;
    $operations //= ['nfc', 'lowercase'];
    
    for my $op (@$operations) {
        if ($op eq 'nfc') {
            $text = NFC($text);
        }
        elsif ($op eq 'nfd') {
            $text = NFD($text);
        }
        elsif ($op eq 'lowercase') {
            $text = lc $text;
        }
        elsif ($op eq 'strip_diacritics') {
            $text = unidecode($text);
        }
        elsif ($op eq 'strip_punctuation') {
            $text =~ s/[[:punct:]]//g;
        }
    }
    
    return $text;
}

sub extract_ipa_from_kirshenbaum {
    my ($self, $text) = @_;
    
    # Kirshenbaum to IPA mapping
    my %k2ipa = (
        'S'  => 'ʃ',
        'Z'  => 'ʒ',
        'T'  => 'θ',
        'D'  => 'ð',
        'N'  => 'ŋ',
        '@'  => 'ə',
        '3'  => 'ɜ',
        'A'  => 'ɑ',
    );
    
    my $ipa = $text;
    for my $k (keys %k2ipa) {
        $ipa =~ s/\Q$k\E/$k2ipa{$k}/g;
    }
    
    return $ipa;
}

sub validate_ipa {
    my ($self, $ipa) = @_;
    
    # Use Lingua::IPA for validation
    eval {
        $self->{ipa_validator}->parse($ipa);
        return 1;
    };
    
    return 0 if $@;
    return 1;
}

1;

__END__

=head1 DESCRIPTION

High-performance dictionary parsing using Perl's optimized regex engine.
Handles messy, inconsistent linguistic data from various sources.

=cut

